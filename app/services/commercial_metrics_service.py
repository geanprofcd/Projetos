from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.services.funnel_service import list_funnels
from app.services.metadata_service import list_internal_users
from app.services.opportunity_service import list_opportunities, list_lost_reasons
from app.services.product_service import money_label, money_storage, parse_money


def _parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _period(start_date: str | date | None, end_date: str | date | None) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    end = _parse_date(end_date) or today
    start = _parse_date(start_date) or (end - timedelta(days=29))
    if start > end:
        start, end = end, start
    return start, end


def _closed_on(row: dict) -> date | None:
    stamp = row.get("won_at") if row.get("status") == "won" else row.get("lost_at") if row.get("status") == "lost" else None
    parsed = _parse_datetime(stamp)
    return parsed.date() if parsed else None


def _matches_scope(row: dict, *, funnel_id: str | None, assigned_user_id: str | None) -> bool:
    if funnel_id and str(row.get("funnel_id") or "") != str(funnel_id):
        return False
    if assigned_user_id and str(row.get("assigned_user_id") or "") != str(assigned_user_id):
        return False
    return True


def _bar_percent(value: Decimal, maximum: Decimal) -> int:
    if maximum <= 0:
        return 0
    return max(2, min(100, int((value / maximum) * Decimal("100")))) if value > 0 else 0


def commercial_indicators(
    *,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    funnel_id: str | None = None,
    assigned_user_id: str | None = None,
) -> dict:
    """Calcula indicadores comerciais sem tratar oportunidade aberta como venda.

    Pipeline usa oportunidades abertas no estado atual. Receita, conversão e ticket
    médio usam somente oportunidades ganhas no período. Perdidas entram apenas no
    denominador de conversão e nas análises de perda.
    """
    start, end = _period(start_date, end_date)
    rows = [
        row
        for row in list_opportunities(status="all")
        if _matches_scope(row, funnel_id=funnel_id, assigned_user_id=assigned_user_id)
    ]

    open_rows = [row for row in rows if row.get("status") == "open"]
    closed_rows = [
        row
        for row in rows
        if row.get("status") in {"won", "lost"}
        and (closed := _closed_on(row)) is not None
        and start <= closed <= end
    ]
    won_rows = [row for row in closed_rows if row.get("status") == "won"]
    lost_rows = [row for row in closed_rows if row.get("status") == "lost"]

    pipeline_value = sum((parse_money(row.get("calculated_value")) for row in open_rows), Decimal("0.00"))
    won_value = sum((parse_money(row.get("final_value")) for row in won_rows), Decimal("0.00"))
    closed_count = len(won_rows) + len(lost_rows)
    conversion = (Decimal(len(won_rows)) / Decimal(closed_count) * Decimal("100")) if closed_count else Decimal("0.00")
    avg_ticket = (won_value / Decimal(len(won_rows))) if won_rows else Decimal("0.00")

    funnels = list_funnels(include_inactive=True)
    funnel_map = {str(row.get("id")): row for row in funnels}
    stage_rows: list[dict] = []
    for funnel in funnels:
        if funnel_id and str(funnel.get("id")) != str(funnel_id):
            continue
        for stage in funnel.get("stages") or []:
            scoped = [row for row in open_rows if str(row.get("stage_id")) == str(stage.get("id"))]
            value = sum((parse_money(row.get("calculated_value")) for row in scoped), Decimal("0.00"))
            if scoped or bool(stage.get("is_active", True)):
                stage_rows.append(
                    {
                        "funnel_id": str(funnel.get("id")),
                        "funnel_name": funnel.get("name") or "Funil",
                        "stage_id": str(stage.get("id")),
                        "stage_name": stage.get("name") or "Etapa",
                        "stage_color": stage.get("color") or "#94a3b8",
                        "position": int(stage.get("position") or 0),
                        "count": len(scoped),
                        "value": money_storage(value),
                        "value_label": money_label(value),
                        "_value_decimal": value,
                    }
                )
    max_stage_value = max((row["_value_decimal"] for row in stage_rows), default=Decimal("0.00"))
    for row in stage_rows:
        row["bar_percent"] = _bar_percent(row.pop("_value_decimal"), max_stage_value)
    stage_rows.sort(key=lambda row: (row["funnel_name"].casefold(), row["position"], row["stage_name"].casefold()))

    users = list_internal_users()
    user_ids = {str(row.get("id")) for row in users}
    if assigned_user_id and str(assigned_user_id) not in user_ids:
        users = []
    performance = []
    for user in users:
        uid = str(user.get("id"))
        if assigned_user_id and uid != str(assigned_user_id):
            continue
        user_open = [row for row in open_rows if str(row.get("assigned_user_id") or "") == uid]
        user_won = [row for row in won_rows if str(row.get("assigned_user_id") or "") == uid]
        user_lost = [row for row in lost_rows if str(row.get("assigned_user_id") or "") == uid]
        user_pipeline = sum((parse_money(row.get("calculated_value")) for row in user_open), Decimal("0.00"))
        user_won_value = sum((parse_money(row.get("final_value")) for row in user_won), Decimal("0.00"))
        user_closed = len(user_won) + len(user_lost)
        user_conversion = (Decimal(len(user_won)) / Decimal(user_closed) * Decimal("100")) if user_closed else Decimal("0.00")
        performance.append(
            {
                "id": uid,
                "name": user.get("full_name") or "Responsável",
                "open_count": len(user_open),
                "pipeline_label": money_label(user_pipeline),
                "won_count": len(user_won),
                "won_value_label": money_label(user_won_value),
                "lost_count": len(user_lost),
                "conversion_label": f"{user_conversion.quantize(Decimal('0.1'))}%".replace(".", ","),
                "_won_value": user_won_value,
            }
        )
    performance.sort(key=lambda row: (row["_won_value"], row["won_count"], row["name"].casefold()), reverse=True)
    for row in performance:
        row.pop("_won_value", None)

    reason_map = {str(row.get("id")): row.get("name") or "Outro" for row in list_lost_reasons(active_only=False)}
    reason_counts: dict[str, int] = defaultdict(int)
    for row in lost_rows:
        reason_counts[reason_map.get(str(row.get("lost_reason_id")), "Sem motivo informado")] += 1
    max_reason = max(reason_counts.values(), default=0)
    losses = [
        {
            "name": name,
            "count": count,
            "bar_percent": int((count / max_reason) * 100) if max_reason else 0,
        }
        for name, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    ]

    funnel_options = [{"id": str(row.get("id")), "name": row.get("name") or "Funil"} for row in funnels]
    responsible_options = [{"id": str(row.get("id")), "name": row.get("full_name") or "Responsável"} for row in list_internal_users()]

    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "period_label": f"{start.strftime('%d/%m/%Y')} a {end.strftime('%d/%m/%Y')}",
        "pipeline_count": len(open_rows),
        "pipeline_value": money_storage(pipeline_value),
        "pipeline_value_label": money_label(pipeline_value),
        "won_count": len(won_rows),
        "won_value": money_storage(won_value),
        "won_value_label": money_label(won_value),
        "lost_count": len(lost_rows),
        "closed_count": closed_count,
        "conversion_percent": float(conversion),
        "conversion_label": f"{conversion.quantize(Decimal('0.1'))}%".replace(".", ","),
        "avg_ticket": money_storage(avg_ticket),
        "avg_ticket_label": money_label(avg_ticket),
        "stage_rows": stage_rows,
        "performance": performance,
        "loss_reasons": losses,
        "funnels": funnel_options,
        "responsibles": responsible_options,
        "selected_funnel_id": str(funnel_id or ""),
        "selected_assigned_user_id": str(assigned_user_id or ""),
    }
