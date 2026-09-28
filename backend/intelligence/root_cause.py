from typing import Any, Dict, List


def analyze(current_evidence: Dict[str, Any], historical: List[Dict[str, Any]]) -> Dict[str, Any]:
    history = current_evidence.get("history", [])
    failures = [r for r in history if r.get("status") == "failed"]
    commits = current_evidence.get("related_commits", [])
    incidents = current_evidence.get("related_incidents", [])
    signals: List[Dict[str, str]] = []

    if len(failures) >= 3:
        signals.append({
            "signal": "Repeated failure pattern",
            "evidence": f"{len(failures)} failed CI runs are recorded for this test.",
            "strength": "strong",
        })
    elif failures:
        signals.append({
            "signal": "Recent failure",
            "evidence": "At least one recent CI run failed for this test.",
            "strength": "moderate",
        })

    if commits:
        signals.append({
            "signal": "Recent code change",
            "evidence": f"{len(commits)} related commit(s) were found in the local evidence store.",
            "strength": "moderate",
        })

    if incidents:
        signals.append({
            "signal": "Related service incident",
            "evidence": f"{len(incidents)} incident(s) are recorded for the same service.",
            "strength": "strong",
        })

    regression_memories = [m for m in historical if str(m.get("outcome", "")).lower() == "real_regression"]
    if regression_memories:
        signals.append({
            "signal": "Historical regression experience",
            "evidence": f"Hindsight recalled {len(regression_memories)} relevant experience(s) that ended in a real regression.",
            "strength": "strong",
        })

    if incidents:
        summary = "Current CI failures overlap with a related service incident, so the evidence deserves investigation."
    elif commits and len(failures) >= 3:
        summary = "Repeated failures overlap with recent code changes, making a regression investigation reasonable."
    elif historical:
        summary = "Historical engineering experience adds context to the current failure."
    elif failures:
        summary = "The test has recent failure evidence, but the available context is limited."
    else:
        summary = "There is not enough evidence yet to identify a likely cause."

    return {
        "summary": summary,
        "signals": signals,
        "caveat": "These signals describe evidence and timing; they do not prove causation by themselves.",
    }
