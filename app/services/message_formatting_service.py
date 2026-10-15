from __future__ import annotations

import re

_ROUTE_SUFFIX_RE = re.compile(r"(?:\s*\n?\s*)(#[123])\s*$")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?…])\s+(?=(?:[\"'“‘(\[])?[A-ZÀ-ÖØ-Þ0-9])")
_MULTI_BLANK_RE = re.compile(r"\n[\t ]*\n(?:[\t ]*\n)+")

# Abreviações comuns que não devem ser tratadas como fim de ideia durante a
# humanização automática. O algoritmo nunca reescreve palavras: apenas decide
# em quais espaços pode inserir uma linha em branco.
_ABBREVIATIONS = {
    "sr.", "sra.", "srta.", "dr.", "dra.", "prof.", "profa.", "etc.",
    "ex.", "aprox.", "obs.", "tel.", "av.", "r.", "nº.", "no.",
}


def _clean_existing_breaks(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in value.split("\n")]
    value = "\n".join(lines).strip()
    return _MULTI_BLANK_RE.sub("\n\n", value)


def _split_sentences(single_line: str) -> list[str]:
    """Split only on safe sentence boundaries while preserving the text itself."""
    pieces: list[str] = []
    start = 0
    for match in _SENTENCE_BOUNDARY_RE.finditer(single_line):
        candidate = single_line[start:match.start()].strip()
        tail_word = candidate.rsplit(" ", 1)[-1].lower() if candidate else ""
        if tail_word in _ABBREVIATIONS:
            continue
        # Evita quebrar depois de iniciais como "A." / "J.".
        if re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ]\.", tail_word):
            continue
        if candidate:
            pieces.append(candidate)
            start = match.end()
    tail = single_line[start:].strip()
    if tail:
        pieces.append(tail)
    return pieces or [single_line.strip()]


def _group_sentences(sentences: list[str], *, soft_limit: int = 220) -> list[str]:
    """Build WhatsApp-like paragraphs without changing sentence contents."""
    if len(sentences) <= 1:
        return sentences

    paragraphs: list[str] = []
    current = ""
    for sentence in sentences:
        if not current:
            current = sentence
            continue
        joined = f"{current} {sentence}"
        # Prefer 1–2 sentences per block. Questions naturally start a new block
        # when the previous block already contains a complete thought.
        current_sentence_count = len(_split_sentences(current))
        should_break = len(joined) > soft_limit or current_sentence_count >= 2 or current.rstrip().endswith("?")
        if should_break:
            paragraphs.append(current)
            current = sentence
        else:
            current = joined
    if current:
        paragraphs.append(current)
    return paragraphs


def normalize_ai_message(message: str) -> tuple[str, bool]:
    """Return a display-safe, humanized AI message and whether it was changed.

    Rules:
    - existing paragraphs are preserved (only line-ending/trailing-space cleanup);
    - single-line long answers are split only at punctuation boundaries;
    - URLs, numbers, emojis and words are never rewritten;
    - a trailing technical #1/#2/#3 marker, if present, remains on its own line.
    """
    original = str(message or "")
    cleaned = _clean_existing_breaks(original)
    if not cleaned:
        return "", cleaned != original

    route_suffix: str | None = None
    route_match = _ROUTE_SUFFIX_RE.search(cleaned)
    if route_match:
        route_suffix = route_match.group(1)
        cleaned = cleaned[:route_match.start()].rstrip()

    # Se o agente já formatou a conversa em blocos, o VENDRA não tenta ser
    # "mais inteligente" que o texto recebido: apenas normaliza excesso de linhas.
    if "\n" in cleaned:
        formatted = cleaned
    else:
        sentences = _split_sentences(cleaned)
        # Textos curtos e de uma ideia só não ganham quebra artificial.
        if len(cleaned) < 150 or len(sentences) < 2:
            formatted = cleaned
        else:
            formatted = "\n\n".join(_group_sentences(sentences))

    if route_suffix:
        formatted = f"{formatted}\n\n{route_suffix}" if formatted else route_suffix

    formatted = _clean_existing_breaks(formatted)
    return formatted, formatted != original
