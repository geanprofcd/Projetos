"""Smoke local VENDRA 0.0.14: normalização conservadora de mensagens da IA."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.message_formatting_service import normalize_ai_message


def main() -> None:
    raw = (
        "Oi, Gean! Tudo bem? 👋 A i9se trabalha ajudando empresas a organizar melhor gestão, processos e resultados. "
        "Hoje o que mais tem exigido atenção por aí: equipe, processos ou financeiro? 😊"
    )
    formatted, changed = normalize_ai_message(raw)
    assert changed is True
    assert "\n\n" in formatted
    assert formatted.replace("\n\n", " ") == raw
    assert "👋" in formatted and "😊" in formatted

    already = "Oi, Gean! Tudo bem? 👋\n\nPosso te explicar melhor? 😊"
    kept, _ = normalize_ai_message(already)
    assert kept == already

    protected = "Confira https://exemplo.com/a.b?x=1 e o valor R$ 12.500. Podemos seguir com isso amanhã? 👍"
    result, _ = normalize_ai_message(protected)
    assert "https://exemplo.com/a.b?x=1" in result
    assert "R$ 12.500" in result
    assert "👍" in result

    short = "Oi! Tudo bem? 😊"
    result, changed = normalize_ai_message(short)
    assert result == short and changed is False

    tagged = (
        "Oi, Gean! Tudo bem? Quero te explicar como a i9se pode ajudar na gestão da empresa. "
        "Hoje o que mais pesa por aí: equipe, processos ou financeiro? #2"
    )
    result, _ = normalize_ai_message(tagged)
    assert result.endswith("\n\n#2")
    assert result.count("#2") == 1

    print("VENDRA_MESSAGE_FORMATTING_SMOKE_OK")


if __name__ == "__main__":
    main()
