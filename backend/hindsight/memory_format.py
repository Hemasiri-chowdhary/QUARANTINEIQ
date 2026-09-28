import json
import re
from typing import Any, Dict, Iterable, List

OUTCOME_PATTERNS = {
    "real_regression": re.compile(r"real regression|actual regression", re.I),
    "genuinely_flaky": re.compile(r"genuinely flaky|flaky", re.I),
    "infrastructure_issue": re.compile(r"infrastructure issue|infra", re.I),
    "still_uncertain": re.compile(r"still uncertain|uncertain", re.I),
}

GENERIC_LESSONS = {
    "an engineering decision and experience were retained.",
    "an engineering experience was retained.",
    "quarantineiq engineering experience",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _outcome(text: str):
    for value, pattern in OUTCOME_PATTERNS.items():
        if pattern.search(text):
            return value
    return None


def normalize_memory(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        raw = item.get("raw_content") or item.get("text") or item.get("content")
        if isinstance(raw, dict):
            result = dict(raw)
        elif isinstance(raw, str):
            try:
                parsed = json.loads(raw)
                result = parsed if isinstance(parsed, dict) else _parse_text(raw)
            except (json.JSONDecodeError, TypeError):
                result = _parse_text(raw)
        else:
            result = dict(item)
        for key in ("_score", "relevance_score", "source_count"):
            if key in item:
                result[key] = item[key]
        if "raw_content" not in result and isinstance(raw, str):
            result["raw_content"] = raw
        return result
    text = str(item)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else _parse_text(text)
    except (json.JSONDecodeError, TypeError):
        return _parse_text(text)


def _parse_text(text: str) -> Dict[str, Any]:
    cleaned = " ".join(text.split())
    fields = {
        "test": None, "service": None, "repository": None,
        "failure_type": None, "decision": None, "human_decision": None,
        "outcome": _outcome(cleaned), "lesson": None, "timestamp": None,
        "memory_marker": None, "raw_content": text,
    }
    patterns = {
        "test": r"(?:test(?: named| called)?)\s*[:=]?\s*['\"]?([A-Za-z0-9_.:/-]+)",
        "service": r"(?:service|involving)\s*[:=]?\s*['\"]?([A-Za-z0-9_.:/-]+)",
        "repository": r"repository\s*[:=]?\s*['\"]?([A-Za-z0-9_.:/-]+)",
        "failure_type": r"failure(?: type)?\s*[:=]\s*([A-Za-z0-9_. -]+?)(?:\||$)",
        "timestamp": r"(?:when|recorded|timestamp)\s*[:=]\s*(\d{4}-\d{2}-\d{2}(?:T[^|\s]+)?)",
        "memory_marker": r"(?:memory marker|marker)\s*[:=]\s*([A-Za-z0-9_.:-]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, cleaned, re.I)
        if match:
            fields[key] = match.group(1).strip("'\"")
    match = re.search(r"(?:human )?decision(?: was)?(?: to)?\s*(quarantine|investigate|keep active|keep_active)", cleaned, re.I)
    if match:
        value = match.group(1).lower().replace(" ", "_")
        fields["decision"] = value
        fields["human_decision"] = value
    match = re.search(r"lesson(?: learned)?\s*[:=]\s*(.+?)(?:\||$)", cleaned, re.I)
    if match:
        fields["lesson"] = match.group(1).strip()
    if not fields["lesson"]:
        parts = [p.strip() for p in cleaned.split("|") if p.strip()]
        fields["lesson"] = next((p.split(":", 1)[1].strip() for p in parts if p.lower().startswith("lesson") and ":" in p), None)
        if not fields["lesson"] and parts:
            fields["lesson"] = parts[-1]
    if not fields["test"]:
        match = re.search(r"\b(test_[A-Za-z0-9_]+)\b", cleaned, re.I)
        if match:
            fields["test"] = match.group(1)
    if not fields["service"]:
        match = re.search(r"\b([A-Za-z0-9_-]+-service)\b", cleaned, re.I)
        if match:
            fields["service"] = match.group(1)
    return fields


def _is_useful(item: Dict[str, Any]) -> bool:
    lesson = " ".join(_text(item.get("lesson")).split())
    if lesson.lower() in GENERIC_LESSONS:
        return False
    if re.fullmatch(r"When:\s*\d{4}-\d{2}-\d{2}", lesson, re.I):
        return False
    if lesson.lower().startswith("when:") and len(lesson) < 90:
        return False
    identity = any(_text(item.get(key)) for key in ("test", "service", "repository", "failure_type", "outcome"))
    meaningful_lesson = len(lesson) >= 24
    return identity and meaningful_lesson


def dedupe_memories(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for item in items:
        if not _is_useful(item):
            continue
        marker = _text(item.get("memory_marker")).lower()
        lesson = " ".join(_text(item.get("lesson")).split()).lower()
        test = _text(item.get("test")).lower()
        service = _text(item.get("service")).lower()
        outcome = _text(item.get("outcome")).lower()
        key = marker or "|".join([test, service, outcome, lesson])
        if key not in seen:
            seen[key] = dict(item)
            seen[key]["source_count"] = 1
            order.append(key)
        else:
            seen[key]["source_count"] += 1
            for field in ("timestamp", "service", "test", "repository", "failure_type", "decision", "human_decision", "outcome", "memory_marker", "raw_content", "evidence"):
                if not seen[key].get(field) and item.get(field):
                    seen[key][field] = item[field]
    return [seen[k] for k in order]
