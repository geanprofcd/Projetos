from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4
import atexit
import json
import os
import shutil


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEMO_INTERNAL_USERS = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "full_name": "Administrador Demo",
        "email": "admin@demo.local",
        "role": "administrador",
        "status": "active",
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "full_name": "Marina Responsável",
        "email": "marina@demo.local",
        "role": "responsavel",
        "status": "active",
    },
]

DEMO_USER_INVITATIONS: list[dict] = []
DEMO_USER_PASSWORDS: dict[str, dict] = {}

DEMO_CUSTOMERS = [
    {"id": "c1", "profile_id": None, "name": "João da Silva", "phone": "+55 65 99999-1001", "phone_normalized": "5565999991001", "email": "joao@exemplo.com", "document": None, "company_name": None, "status": "active", "tags": ["soja"], "created_at": "2026-09-04T20:00:00-03:00"},
    {"id": "c2", "profile_id": None, "name": "Carlos Pereira", "phone": "+55 65 99999-1002", "phone_normalized": "5565999991002", "email": "carlos@exemplo.com", "document": None, "company_name": None, "status": "active", "tags": ["milho"], "created_at": "2026-09-04T20:00:00-03:00"},
    {"id": "c3", "profile_id": None, "name": "Pedro Alves", "phone": "+55 66 99999-1003", "phone_normalized": "5566999991003", "email": "pedro@exemplo.com", "document": None, "company_name": None, "status": "active", "tags": ["café"], "created_at": "2026-09-04T20:00:00-03:00"},
]

DEMO_FARMS = [
    {"id": "f1", "customer_id": "c1", "name": "Fazenda Santa Maria", "city": "Sorriso", "state": "MT", "area_hectares": 860.0, "created_at": "2026-09-04T20:00:00-03:00"},
    {"id": "f2", "customer_id": "c2", "name": "Fazenda Horizonte", "city": "Lucas do Rio Verde", "state": "MT", "area_hectares": 540.0, "created_at": "2026-09-04T20:00:00-03:00"},
    {"id": "f3", "customer_id": "c3", "name": "Sítio Boa Vista", "city": "Patrocínio", "state": "MG", "area_hectares": 96.0, "created_at": "2026-09-04T20:00:00-03:00"},
]

DEMO_CROPS = [
    {"id": "crop-soja", "name": "Soja"},
    {"id": "crop-milho", "name": "Milho"},
    {"id": "crop-algodao", "name": "Algodão"},
    {"id": "crop-cafe", "name": "Café"},
    {"id": "crop-cana", "name": "Cana"},
    {"id": "crop-feijao", "name": "Feijão"},
    {"id": "crop-trigo", "name": "Trigo"},
]

DEMO_CATEGORIES = [
    {"id": "cat-plantio", "name": "Plantio"},
    {"id": "cat-adubacao", "name": "Adubação"},
    {"id": "cat-pragas", "name": "Pragas"},
    {"id": "cat-doencas", "name": "Doenças"},
    {"id": "cat-solo", "name": "Análise de solo"},
    {"id": "cat-orcamento", "name": "Orçamento"},
    {"id": "cat-comercial", "name": "Comercial"},
]

DEMO_TICKETS = [
    {
        "id": "1548", "title": "Manchas nas folhas da soja", "status": "em_atendimento", "priority": "alta", "source": "whatsapp",
        "customer_id": "c1", "farm_id": "f1", "crop_id": "crop-soja", "category_id": "cat-doencas", "assigned_user_id": DEMO_INTERNAL_USERS[0]["id"],
        "created_at": "2026-09-04T22:50:00-03:00", "updated_at": "2026-09-04T22:58:00-03:00", "closed_at": None,
    },
    {
        "id": "1547", "title": "Orçamento para fertilizante", "status": "aguardando_orcamento", "priority": "normal", "source": "portal",
        "customer_id": "c2", "farm_id": "f2", "crop_id": "crop-milho", "category_id": "cat-orcamento", "assigned_user_id": DEMO_INTERNAL_USERS[0]["id"],
        "created_at": "2026-09-04T22:30:00-03:00", "updated_at": "2026-09-04T22:41:00-03:00", "closed_at": None,
    },
    {
        "id": "1546", "title": "Dúvida sobre análise de solo", "status": "novo", "priority": "normal", "source": "whatsapp",
        "customer_id": "c3", "farm_id": "f3", "crop_id": "crop-cafe", "category_id": "cat-solo", "assigned_user_id": None,
        "created_at": "2026-09-04T22:20:00-03:00", "updated_at": "2026-09-04T22:22:00-03:00", "closed_at": None,
    },
]

DEMO_MESSAGES = {
    "1548": [
        {"id": "m1", "sender_id": "c1", "sender_name": "João da Silva", "body": "Bom dia, estou encontrando essas manchas na lavoura. Posso enviar algumas fotos?", "created_at": "2026-09-04T22:52:00-03:00", "is_internal": False, "channel": "whatsapp", "direction": "inbound"},
        {"id": "m2", "sender_id": DEMO_INTERNAL_USERS[0]["id"], "sender_name": "Administrador Demo", "body": "Claro. Envie fotos próximas das folhas e, se possível, informe o estágio da soja.", "created_at": "2026-09-04T22:55:00-03:00", "is_internal": False, "channel": "internal", "direction": "outbound"},
        {"id": "m3", "sender_id": "c1", "sender_name": "João da Silva", "body": "Está em V6. Vou encaminhar as imagens agora.", "created_at": "2026-09-04T22:58:00-03:00", "is_internal": False, "channel": "whatsapp", "direction": "inbound"},
    ]
}

DEMO_INTEGRATION_EVENTS: dict[str, dict] = {}
DEMO_AUDIT_LOG: list[dict] = []
DEMO_ATTACHMENTS: dict[str, list[dict]] = {}
DEMO_WHATSAPP_OUTBOX: list[dict] = []

# Solicitações de Disparos iniciadas pelo VENDRA e entregues ao Make.
DEMO_DISPATCHES: list[dict] = []
DEMO_DISPATCH_IMPORT_BATCHES: list[dict] = []
DEMO_DISPATCH_IMPORT_ITEMS: list[dict] = []

# Catálogo comercial inicial do VENDRA. Valores monetários são persistidos
# como texto decimal para preservar precisão no modo local/demo.
DEMO_PRODUCTS = [
    {
        "id": "product-demo-1",
        "kind": "service",
        "code": "SERV-001",
        "name": "Consultoria",
        "description": "Serviço demonstrativo do catálogo comercial.",
        "category": "Serviços",
        "unit": "serviço",
        "default_price": "5000.00",
        "is_active": True,
        "created_at": "2026-10-04T18:45:00+00:00",
        "updated_at": "2026-10-04T18:45:00+00:00",
    },
    {
        "id": "product-demo-2",
        "kind": "service",
        "code": "SERV-002",
        "name": "Implantação",
        "description": "Serviço demonstrativo para composição futura de oportunidades.",
        "category": "Serviços",
        "unit": "projeto",
        "default_price": "7500.00",
        "is_active": True,
        "created_at": "2026-10-04T18:45:00+00:00",
        "updated_at": "2026-10-04T18:45:00+00:00",
    },
]

# Funis comerciais configuráveis do VENDRA. As oportunidades serão vinculadas
# a estas entidades no próximo incremento.
DEMO_SALES_FUNNELS = [
    {
        "id": "funnel-demo-commercial",
        "name": "Funil Comercial",
        "description": "Fluxo comercial padrão para demonstração e homologação do CRM.",
        "is_active": True,
        "created_at": "2026-10-04T19:30:00+00:00",
        "updated_at": "2026-10-04T19:30:00+00:00",
    },
]

DEMO_FUNNEL_STAGES = [
    {"id": "stage-demo-1", "funnel_id": "funnel-demo-commercial", "name": "Novo lead", "position": 1, "color": "#64748b", "is_active": True, "created_at": "2026-10-04T19:30:00+00:00", "updated_at": "2026-10-04T19:30:00+00:00"},
    {"id": "stage-demo-2", "funnel_id": "funnel-demo-commercial", "name": "Qualificação", "position": 2, "color": "#3157d5", "is_active": True, "created_at": "2026-10-04T19:30:00+00:00", "updated_at": "2026-10-04T19:30:00+00:00"},
    {"id": "stage-demo-3", "funnel_id": "funnel-demo-commercial", "name": "Proposta", "position": 3, "color": "#7c3aed", "is_active": True, "created_at": "2026-10-04T19:30:00+00:00", "updated_at": "2026-10-04T19:30:00+00:00"},
    {"id": "stage-demo-4", "funnel_id": "funnel-demo-commercial", "name": "Negociação", "position": 4, "color": "#d97706", "is_active": True, "created_at": "2026-10-04T19:30:00+00:00", "updated_at": "2026-10-04T19:30:00+00:00"},
    {"id": "stage-demo-5", "funnel_id": "funnel-demo-commercial", "name": "Fechamento", "position": 5, "color": "#15803d", "is_active": True, "created_at": "2026-10-04T19:30:00+00:00", "updated_at": "2026-10-04T19:30:00+00:00"},
]


# Oportunidades comerciais do VENDRA. O valor é sempre derivado dos itens;
# não existe valor manual concorrente na v0.1.
DEMO_LOST_REASONS = [
    {"id": "lost-price", "name": "Preço", "is_active": True},
    {"id": "lost-competitor", "name": "Concorrente", "is_active": True},
    {"id": "lost-budget", "name": "Sem orçamento", "is_active": True},
    {"id": "lost-no-response", "name": "Sem retorno", "is_active": True},
    {"id": "lost-deadline", "name": "Prazo", "is_active": True},
    {"id": "lost-cancelled", "name": "Desistência", "is_active": True},
    {"id": "lost-other", "name": "Outro", "is_active": True},
]

DEMO_OPPORTUNITIES = [
    {
        "id": "opportunity-demo-1",
        "customer_id": "c2",
        "ticket_id": "1547",
        "title": "Implantação e consultoria comercial",
        "funnel_id": "funnel-demo-commercial",
        "stage_id": "stage-demo-3",
        "assigned_user_id": DEMO_INTERNAL_USERS[0]["id"],
        "status": "open",
        "currency_code": "BRL",
        "calculated_value": "12500.00",
        "final_value": None,
        "expected_close_date": "2026-10-20",
        "won_at": None,
        "lost_at": None,
        "lost_reason_id": None,
        "lost_notes": None,
        "kanban_position": 1000,
        "lock_version": 1,
        "archived_at": None,
        "archived_by": None,
        "created_at": "2026-10-04T20:00:00+00:00",
        "updated_at": "2026-10-04T20:00:00+00:00",
    },
]

DEMO_OPPORTUNITY_ITEMS = [
    {
        "id": "opportunity-item-demo-1",
        "opportunity_id": "opportunity-demo-1",
        "product_id": "product-demo-1",
        "name_snapshot": "Consultoria",
        "description_snapshot": "Serviço demonstrativo do catálogo comercial.",
        "unit_snapshot": "serviço",
        "quantity": "1.0000",
        "unit_price": "5000.00",
        "discount_amount": "0.00",
        "subtotal": "5000.00",
        "line_position": 1,
        "created_at": "2026-10-04T20:00:00+00:00",
        "updated_at": "2026-10-04T20:00:00+00:00",
    },
    {
        "id": "opportunity-item-demo-2",
        "opportunity_id": "opportunity-demo-1",
        "product_id": "product-demo-2",
        "name_snapshot": "Implantação",
        "description_snapshot": "Serviço demonstrativo para composição futura de oportunidades.",
        "unit_snapshot": "projeto",
        "quantity": "1.0000",
        "unit_price": "7500.00",
        "discount_amount": "0.00",
        "subtotal": "7500.00",
        "line_position": 2,
        "created_at": "2026-10-04T20:00:00+00:00",
        "updated_at": "2026-10-04T20:00:00+00:00",
    },
]

DEMO_OPPORTUNITY_STAGE_HISTORY = [
    {
        "id": "stage-history-demo-1",
        "opportunity_id": "opportunity-demo-1",
        "from_stage_id": None,
        "to_stage_id": "stage-demo-3",
        "moved_by": DEMO_INTERNAL_USERS[0]["id"],
        "source": "system",
        "moved_at": "2026-10-04T20:00:00+00:00",
    },
]



def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"

# Persistência local do modo demo/teste.
# O arquivo fica em .vendra-data, que é preservado pelo Atualizador Seguro.
ROOT = Path(__file__).resolve().parents[2]
DEMO_STATE_DIR = ROOT / ".vendra-data"
DEMO_STATE_FILE = Path(os.getenv("VENDRA_DEMO_STATE_FILE") or (DEMO_STATE_DIR / "demo_state.json"))
DEMO_STATE_DIR = DEMO_STATE_FILE.parent
_DEMO_STATE_LOCK = RLock()


def _state_payload() -> dict:
    return {
        "schema_version": 7,
        "saved_at": now_iso(),
        "customers": DEMO_CUSTOMERS,
        "internal_users": DEMO_INTERNAL_USERS,
        "user_invitations": DEMO_USER_INVITATIONS,
        "user_passwords": DEMO_USER_PASSWORDS,
        "farms": DEMO_FARMS,
        "tickets": DEMO_TICKETS,
        "messages": DEMO_MESSAGES,
        "integration_events": DEMO_INTEGRATION_EVENTS,
        "audit_log": DEMO_AUDIT_LOG,
        "attachments": DEMO_ATTACHMENTS,
        "whatsapp_outbox": DEMO_WHATSAPP_OUTBOX,
        "dispatches": DEMO_DISPATCHES,
        "dispatch_import_batches": DEMO_DISPATCH_IMPORT_BATCHES,
        "dispatch_import_items": DEMO_DISPATCH_IMPORT_ITEMS,
        "products": DEMO_PRODUCTS,
        "sales_funnels": DEMO_SALES_FUNNELS,
        "funnel_stages": DEMO_FUNNEL_STAGES,
        "lost_reasons": DEMO_LOST_REASONS,
        "opportunities": DEMO_OPPORTUNITIES,
        "opportunity_items": DEMO_OPPORTUNITY_ITEMS,
        "opportunity_stage_history": DEMO_OPPORTUNITY_STAGE_HISTORY,
    }


def persist_demo_state() -> None:
    """Grava o estado operacional do modo demo de forma atômica.

    O arquivo não contém tokens da Meta nem o segredo do webhook; essas
    credenciais permanecem no armazenamento local específico já existente.
    """
    with _DEMO_STATE_LOCK:
        DEMO_STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = DEMO_STATE_FILE.with_suffix(".json.tmp")
        data = json.dumps(_state_payload(), ensure_ascii=False, indent=2)
        tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, DEMO_STATE_FILE)


def _replace_list(target: list, value) -> None:
    if isinstance(value, list):
        target[:] = value


def _replace_dict(target: dict, value) -> None:
    if isinstance(value, dict):
        target.clear()
        target.update(value)


def load_demo_state() -> bool:
    """Carrega dados de teste persistidos, quando existentes.

    Em caso de arquivo corrompido, preserva uma cópia para diagnóstico e
    continua com os dados demo padrão em vez de impedir a inicialização.
    """
    if not DEMO_STATE_FILE.exists():
        return False
    with _DEMO_STATE_LOCK:
        try:
            payload = json.loads(DEMO_STATE_FILE.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("estado local inválido")
            _replace_list(DEMO_INTERNAL_USERS, payload.get("internal_users"))
            _replace_list(DEMO_USER_INVITATIONS, payload.get("user_invitations"))
            _replace_dict(DEMO_USER_PASSWORDS, payload.get("user_passwords"))
            _replace_list(DEMO_CUSTOMERS, payload.get("customers"))
            _replace_list(DEMO_FARMS, payload.get("farms"))
            _replace_list(DEMO_TICKETS, payload.get("tickets"))
            _replace_dict(DEMO_MESSAGES, payload.get("messages"))
            _replace_dict(DEMO_INTEGRATION_EVENTS, payload.get("integration_events"))
            _replace_list(DEMO_AUDIT_LOG, payload.get("audit_log"))
            _replace_dict(DEMO_ATTACHMENTS, payload.get("attachments"))
            _replace_list(DEMO_WHATSAPP_OUTBOX, payload.get("whatsapp_outbox"))
            _replace_list(DEMO_DISPATCHES, payload.get("dispatches"))
            _replace_list(DEMO_DISPATCH_IMPORT_BATCHES, payload.get("dispatch_import_batches"))
            _replace_list(DEMO_DISPATCH_IMPORT_ITEMS, payload.get("dispatch_import_items"))
            _replace_list(DEMO_PRODUCTS, payload.get("products"))
            _replace_list(DEMO_SALES_FUNNELS, payload.get("sales_funnels"))
            _replace_list(DEMO_FUNNEL_STAGES, payload.get("funnel_stages"))
            _replace_list(DEMO_LOST_REASONS, payload.get("lost_reasons"))
            _replace_list(DEMO_OPPORTUNITIES, payload.get("opportunities"))
            _replace_list(DEMO_OPPORTUNITY_ITEMS, payload.get("opportunity_items"))
            _replace_list(DEMO_OPPORTUNITY_STAGE_HISTORY, payload.get("opportunity_stage_history"))
            return True
        except Exception:
            try:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                backup = DEMO_STATE_FILE.with_name(f"demo_state.corrompido-{stamp}.json")
                shutil.copy2(DEMO_STATE_FILE, backup)
            except Exception:
                pass
            return False


# A carga acontece durante a importação, antes de os serviços consumirem as
# coleções DEMO_*. A gravação ao encerrar é uma proteção adicional; durante a
# execução, o middleware salva ao final de cada requisição HTTP.
load_demo_state()
atexit.register(persist_demo_state)

