from __future__ import annotations

import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("DEMO_MODE", "true")

from app.services.demo_store import DEMO_INTERNAL_USERS, DEMO_TICKETS, DEMO_WHATSAPP_OUTBOX
from app.services.ticket_service import claim_ticket_on_open, list_messages


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    template = (ROOT / "app/templates/tickets/detail.html").read_text(encoding="utf-8")
    js = (ROOT / "app/static/js/ticket-detail-v0.0.18.js").read_text(encoding="utf-8")
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")

    check("<h1>{{ ticket.customer_name }}</h1>" in template, "Cabeçalho deve usar somente o nome do cliente.")
    check("ATENDIMENTO #" not in template, "Identificador textual do atendimento não deve aparecer no cabeçalho.")
    check('action="/atendimentos/{{ ticket.id }}/atribuir"' not in template, "Seletor manual de responsável deve sair da tela.")
    check("Nota interna" not in template, "Nota interna demarcada deve sair do compositor.")
    check("💼 Comercial" not in template, "Botão Comercial demarcado deve sair do compositor.")
    check('>COMERCIAL</span>' not in template, "Título COMERCIAL demarcado deve sair da lateral.")
    check("Até 6 arquivos por mensagem" not in template, "Nota longa de limites deve sair da tela.")
    check("Assistente de IA" in template and " · IA" not in template, "Autoria da IA deve aparecer somente como Assistente de IA.")
    check("WhatsApp:" not in template and "WhatsApp:" not in js, "Status da mensagem não deve manter o prefixo WhatsApp.")
    check("return 'Lido'" in js and "return 'Enviado'" in js, "JS deve traduzir read/sent para Lido/Enviado.")
    check("vendra-v0.0.18.css" in base, "CSS da 0.0.18 deve estar carregado.")

    ticket = next(row for row in DEMO_TICKETS if row["id"] == "1546")
    snapshot = ticket.copy()
    admin = DEMO_INTERNAL_USERS[0].copy()
    second = DEMO_INTERNAL_USERS[1].copy()
    try:
        ticket["assigned_user_id"] = None
        ticket["status"] = "novo"
        first = claim_ticket_on_open("1546", admin)
        check(first.get("assigned_user_id") == admin["id"], "Primeiro usuário interno deve assumir ticket sem responsável.")
        check(first.get("status") == "em_atendimento", "Ticket novo assumido deve entrar em atendimento.")
        again = claim_ticket_on_open("1546", second)
        check(again.get("assigned_user_id") == admin["id"], "Segundo usuário não pode roubar responsabilidade já atribuída.")
    finally:
        ticket.clear(); ticket.update(snapshot)

    # Falhas do provedor podem expor o detalhe sem migration nova, usando last_error da outbox.
    outbox_snapshot = list(DEMO_WHATSAPP_OUTBOX)
    try:
        DEMO_WHATSAPP_OUTBOX.clear()
        DEMO_WHATSAPP_OUTBOX.append({
            "id": "outbox-smoke",
            "ticket_id": "1548",
            "message_id": "m2",
            "status": "failed",
            "last_error": "Falha simulada do provedor",
        })
        rows = list_messages("1548", admin)
        msg = next(row for row in rows if str(row.get("id")) == "m2")
        check(msg.get("delivery_error") == "Falha simulada do provedor", "Erro da outbox deve enriquecer a mensagem.")
    finally:
        DEMO_WHATSAPP_OUTBOX.clear(); DEMO_WHATSAPP_OUTBOX.extend(outbox_snapshot)

    print("ticket_detail_polish_smoke: OK")


if __name__ == "__main__":
    main()
