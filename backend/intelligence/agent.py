from typing import Any, Dict, List


def _text(value: Any) -> str:
    return str(value).lower() if value is not None else ""


def filter_relevant_memories(current_evidence: Dict[str, Any], memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    test = _text(current_evidence.get("test", {}).get("name"))
    service = _text(current_evidence.get("test", {}).get("service"))
    repository = _text(current_evidence.get("test", {}).get("repository"))
    failures = [r for r in current_evidence.get("history", []) if r.get("status") == "failed"]
    failure_types = {_text(r.get("failure_type")) for r in failures if r.get("failure_type")}
    error_terms = set()
    for r in failures[:5]:
        error_terms.update(_text(r.get("error_message")).replace("/", " ").replace(":", " ").split()[:8])
    relevant = []
    for memory in memories:
        blob = _text(memory.get("raw_content") or memory)
        score = 0
        if test and test in blob:
            score += 5
        if service and service in blob:
            score += 3
        if repository and repository in blob:
            score += 1
        if memory.get("test") and _text(memory.get("test")) == test:
            score += 5
        if memory.get("service") and _text(memory.get("service")) == service:
            score += 3
        if memory.get("failure_type") and _text(memory.get("failure_type")) in failure_types:
            score += 3
        if error_terms and any(term in blob for term in list(error_terms)[:6] if len(term) >= 5):
            score += 1
        if score >= 3:
            item = dict(memory)
            item["relevance_score"] = score
            relevant.append(item)
    relevant.sort(key=lambda item: (-int(item.get("relevance_score", 0)), str(item.get("timestamp") or "")))
    return relevant[:8]


def calculate_attention_score(current_evidence: Dict[str, Any], historical_evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    breakdown = {"historical_similarity": 0, "previous_regressions": 0, "recent_code_change": 0, "failure_pattern": 0, "quarantine_age": 0}
    current_test = _text(current_evidence.get("test", {}).get("name"))
    current_service = _text(current_evidence.get("test", {}).get("service"))
    for experience in historical_evidence:
        same_test = _text(experience.get("test")) == current_test and current_test
        same_service = _text(experience.get("service")) == current_service and current_service
        if same_test:
            breakdown["historical_similarity"] = min(25, breakdown["historical_similarity"] + 12)
        elif same_service:
            breakdown["historical_similarity"] = min(25, breakdown["historical_similarity"] + 7)
        elif current_test and current_test in _text(experience.get("raw_content")):
            breakdown["historical_similarity"] = min(25, breakdown["historical_similarity"] + 8)
        if _text(experience.get("outcome")) == "real_regression":
            breakdown["previous_regressions"] = min(30, breakdown["previous_regressions"] + 15)
    if current_evidence.get("related_commits"):
        breakdown["recent_code_change"] = 20
    failures = [r for r in current_evidence.get("history", []) if r.get("status") == "failed"]
    if len(failures) >= 5:
        breakdown["failure_pattern"] = 15
    elif len(failures) >= 2:
        breakdown["failure_pattern"] = 10
    elif failures:
        breakdown["failure_pattern"] = 5
    if _text(current_evidence.get("test", {}).get("status")) == "quarantined":
        breakdown["quarantine_age"] = 5
    return {"score": min(100, sum(breakdown.values())), "breakdown": breakdown}


def get_recommendation_level(score: int) -> str:
    return "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW"


def get_recommendation_message(level: str) -> str:
    return {"HIGH": "Investigate before quarantining.", "MEDIUM": "Review before quarantining.", "LOW": "Quarantine is reasonable."}[level]


def generate_reasoning_summary(current_evidence: Dict[str, Any], historical_evidence: List[Dict[str, Any]], score: int, rec: str) -> str:
    failed = [r for r in current_evidence.get("history", []) if r.get("status") == "failed"]
    failure_type = next((r.get("failure_type") for r in failed if r.get("failure_type")), None)
    signals = []
    if failure_type:
        signals.append(f"{len(failed)} recorded failures include {failure_type}")
    if current_evidence.get("related_commits"):
        signals.append("a recent related code change is present")
    if current_evidence.get("related_incidents"):
        signals.append("a related service incident is present")
    if historical_evidence and any(_text(e.get("outcome")) == "real_regression" for e in historical_evidence):
        signals.append("Hindsight recalled prior experiences that ended in real regressions")
    elif historical_evidence:
        signals.append("Hindsight recalled similar engineering experiences")
    sentence = "; ".join(signals) if signals else "limited supporting signals were available"
    return f"The attention score is {score}/100, so QuarantineIQ recommends {get_recommendation_message(rec)} {sentence.capitalize()}."


def investigate(current_evidence: Dict[str, Any], historical_evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    score_data = calculate_attention_score(current_evidence, historical_evidence)
    level = get_recommendation_level(score_data["score"])
    return {"attention_score": score_data, "recommendation": {"level": level, "message": get_recommendation_message(level)}, "reasoning_summary": generate_reasoning_summary(current_evidence, historical_evidence, score_data["score"], level)}
