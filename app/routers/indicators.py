from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.core.ui import templates
from app.dependencies.auth import current_user, internal_user
from app.services.commercial_metrics_service import commercial_indicators

router = APIRouter(tags=["indicadores"])


@router.get("/indicadores")
def indicators_page(
    request: Request,
    inicio: str | None = None,
    fim: str | None = None,
    funil: str | None = None,
    responsavel: str | None = None,
    user: dict = Depends(current_user),
):
    internal_user(user)
    indicators = commercial_indicators(
        start_date=inicio,
        end_date=fim,
        funnel_id=funil or None,
        assigned_user_id=responsavel or None,
    )
    return templates.TemplateResponse(
        request=request,
        name="indicators.html",
        context={
            "user": user,
            "active_page": "indicators",
            "indicators": indicators,
        },
    )
