import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import models, schemas
from backend.database.session import SessionLocal, get_db
from backend.github import GitHubError, github_is_configured, github_sync
from backend.github.client import GITHUB_REPOSITORY
from backend.hindsight import client as hindsight_client
from backend.hindsight.memory_format import dedupe_memories, normalize_memory
from backend.intelligence import agent as intelligence_agent
from backend.intelligence.root_cause import analyze as analyze_root_cause

router = APIRouter()


def _serialize_test(test: models.Test) -> Dict[str, Any]:
    return schemas.Test.model_validate(test).model_dump(mode="json")


def _build_current_evidence(test_id: int, db: Session) -> Dict[str, Any]:
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    runs = db.query(models.CIRun).filter(models.CIRun.test_id == test_id).order_by(models.CIRun.timestamp.desc()).limit(20).all()
    all_commits = db.query(models.Commit).order_by(models.Commit.timestamp.desc()).limit(100).all()
    service_token = (test.service or "").lower().replace("-service", "")
    name_tokens = [t for t in (test.name or "").lower().replace("test_", "").replace("_", " ").split() if len(t) >= 4]
    related_commits = []
    for commit in all_commits:
        blob = " ".join([commit.message or "", commit.files_changed or "", commit.repository or ""]).lower()
        if service_token and service_token in blob or any(token in blob for token in name_tokens):
            related_commits.append(commit)
        if len(related_commits) >= 8:
            break
    incidents = db.query(models.Incident).filter(models.Incident.service == test.service).order_by(models.Incident.timestamp.desc()).limit(5).all()
    return {
        "test": _serialize_test(test),
        "history": [schemas.CIRun.model_validate(run).model_dump(mode="json") for run in runs],
        "related_commits": [
            {
                "sha": c.sha, "message": c.message, "files": c.files_changed,
                "author": c.author, "timestamp": c.timestamp.isoformat(),
                "repository": c.repository, "url": c.url, "source": c.source,
            }
            for c in related_commits
        ],
        "related_incidents": [
            {
                "title": i.title, "description": i.description, "root_cause": i.root_cause,
                "timestamp": i.timestamp.isoformat(), "source": i.source,
            }
            for i in incidents
        ],
    }


def _build_hindsight_query(current_evidence: Dict[str, Any]) -> str:
    test = current_evidence["test"]
    failed_runs = [r for r in current_evidence["history"] if r.get("status") == "failed"]
    failure_types = sorted({r.get("failure_type") for r in failed_runs if r.get("failure_type")})
    errors = sorted({r.get("error_message") for r in failed_runs if r.get("error_message")})
    commits = [c.get("message") for c in current_evidence["related_commits"] if c.get("message")]
    files = [c.get("files") for c in current_evidence["related_commits"] if c.get("files")]
    incidents = [i.get("root_cause") or i.get("title") for i in current_evidence["related_incidents"] if i.get("root_cause") or i.get("title")]
    return " ".join(str(v) for v in [
        test.get("name"), test.get("service"), test.get("repository"),
        *failure_types, *errors[:3], *commits[:3], *files[:3], *incidents[:3],
    ] if v).strip()


async def _recall_for_evidence(current_evidence: Dict[str, Any], limit: int = 8) -> tuple[List[Dict[str, Any]], str]:
    try:
        memories = await hindsight_client.async_recall_experiences(
            query=_build_hindsight_query(current_evidence),
            limit=limit,
        )
    except hindsight_client.HindsightError as exc:
        return [], f"unavailable: {exc}"
    normalized = dedupe_memories(normalize_memory(memory) for memory in memories)
    relevant = intelligence_agent.filter_relevant_memories(current_evidence, normalized)
    return relevant, "available" if relevant else "No similar historical experience found."


def _challenge_for(test: models.Test, historical: List[Dict[str, Any]], score: int) -> Dict[str, Any]:
    regressions = [m for m in historical if str(m.get("outcome", "")).lower() == "real_regression"]
    triggered = bool(regressions) and score >= 55
    if not triggered:
        return {"triggered": False, "message": None, "evidence_count": 0}
    return {
        "triggered": True,
        "message": f"QuarantineIQ found {len(regressions)} similar historical experience(s) that ended in a real regression. Review the evidence before treating {test.name} as harmless flakiness.",
        "evidence_count": len(regressions),
    }


@router.get("/tests", response_model=List[schemas.Test])
def get_tests(skip: int = 0, limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db)):
    return db.query(models.Test).order_by(models.Test.id.asc()).offset(skip).limit(limit).all()


@router.get("/tests/{test_id}", response_model=schemas.Test)
def get_test(test_id: int, db: Session = Depends(get_db)):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return test


@router.get("/tests/{test_id}/history", response_model=List[schemas.CIRun])
def get_test_history(test_id: int, skip: int = 0, limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db)):
    return db.query(models.CIRun).filter(models.CIRun.test_id == test_id).order_by(models.CIRun.timestamp.desc()).offset(skip).limit(limit).all()


@router.get("/tests/{test_id}/decisions", response_model=List[schemas.Decision])
def get_test_decisions(test_id: int, skip: int = 0, limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db)):
    return db.query(models.Decision).filter(models.Decision.test_id == test_id).order_by(models.Decision.timestamp.desc()).offset(skip).limit(limit).all()


@router.get("/tests/{test_id}/outcomes", response_model=List[schemas.Outcome])
def get_test_outcomes(test_id: int, skip: int = 0, limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db)):
    decision_ids = [row[0] for row in db.query(models.Decision.id).filter(models.Decision.test_id == test_id).all()]
    if not decision_ids:
        return []
    return db.query(models.Outcome).filter(models.Outcome.decision_id.in_(decision_ids)).order_by(models.Outcome.timestamp.desc()).offset(skip).limit(limit).all()


@router.get("/status")
def get_system_status(db: Session = Depends(get_db)):
    tests = db.query(models.Test).all()
    hindsight_available = hindsight_client.hindsight_health()
    memory_count = None
    if hindsight_available:
        try:
            memory_count = len(dedupe_memories(normalize_memory(m) for m in hindsight_client.recall_experiences(
                query="QuarantineIQ engineering decision outcome lesson regression flaky test", limit=40
            )))
        except hindsight_client.HindsightError:
            memory_count = None
    sync = db.query(models.RepositorySync).filter(models.RepositorySync.repository == GITHUB_REPOSITORY).first() if GITHUB_REPOSITORY else None
    return {
        "backend": "healthy",
        "tests": {
            "total": len(tests),
            "quarantined": sum(t.status == models.TestStatus.quarantined for t in tests),
            "active": sum(t.status == models.TestStatus.active for t in tests),
            "disabled": sum(t.status == models.TestStatus.disabled for t in tests),
            "needs_review": sum(t.status == models.TestStatus.needs_review for t in tests),
        },
        "hindsight": {
            "available": hindsight_available,
            "url": hindsight_client.HINDSIGHT_URL,
            "bank_id": hindsight_client.HINDSIGHT_BANK_ID,
            "memory_count": memory_count,
        },
        "github": {
            "configured": github_is_configured(),
            "repository": GITHUB_REPOSITORY or None,
            "last_sync_at": sync.last_sync_at.isoformat() if sync and sync.last_sync_at else None,
            "last_status": sync.last_status if sync else "never_synced",
            "last_error": sync.last_error if sync else None,
        },
    }


@router.get("/memory")
def get_memory(query: str = "QuarantineIQ engineering decision outcome lesson regression flaky test"):
    try:
        raw = hindsight_client.recall_experiences(query=query, limit=60)
    except hindsight_client.HindsightError as exc:
        return {"memory_status": f"unavailable: {exc}", "memories": []}
    memories = dedupe_memories(normalize_memory(m) for m in raw)
    return {"memory_status": "available" if memories else "No retained experiences found.", "memories": memories}


@router.get("/patterns", response_model=List[schemas.Pattern])
def get_patterns(db: Session = Depends(get_db)):
    rows = (
        db.query(models.CIRun.failure_type, func.count(models.CIRun.id))
        .filter(models.CIRun.status == "failed", models.CIRun.failure_type.isnot(None))
        .group_by(models.CIRun.failure_type)
        .order_by(func.count(models.CIRun.id).desc())
        .all()
    )
    patterns: List[schemas.Pattern] = []
    for failure_type, count in rows:
        if count < 2:
            continue
        affected = (
            db.query(models.Test)
            .join(models.CIRun, models.CIRun.test_id == models.Test.id)
            .filter(models.CIRun.failure_type == failure_type)
            .distinct().all()
        )
        regression_count = 0
        examples: List[Dict[str, Any]] = []
        for test in affected:
            decisions = db.query(models.Decision).filter(models.Decision.test_id == test.id).all()
            for decision in decisions:
                outcomes = db.query(models.Outcome).filter(
                    models.Outcome.decision_id == decision.id,
                    models.Outcome.outcome == models.OutcomeType.real_regression,
                ).all()
                regression_count += len(outcomes)
                for outcome in outcomes[:2]:
                    examples.append({"test": test.name, "service": test.service, "outcome": outcome.outcome.value, "timestamp": outcome.timestamp.isoformat()})
        strength = "strong" if regression_count else "observed"
        patterns.append(schemas.Pattern(
            pattern=f"Recurring {failure_type.replace('_', ' ')} failures",
            description=f"The workspace has recorded {count} failed CI runs with the {failure_type.replace('_', ' ')} pattern.",
            count=count,
            affected_tests=[t.name for t in affected[:10]],
            affected_services=sorted({t.service for t in affected})[:10],
            real_regression_count=regression_count,
            examples=examples[:5],
            signal_strength=strength,
        ))
    return patterns[:10]


@router.get("/activity", response_model=List[schemas.ActivityItem])
def get_activity(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    items: List[schemas.ActivityItem] = []
    for run in db.query(models.CIRun).order_by(models.CIRun.timestamp.desc()).limit(limit).all():
        test = db.query(models.Test).filter(models.Test.id == run.test_id).first()
        if not test:
            continue
        items.append(schemas.ActivityItem(kind="ci_failure" if run.status == "failed" else "ci_run", title=f"{test.name} {run.status}", detail=run.error_message or f"{run.source} CI run", timestamp=run.timestamp, source=run.source, url=run.html_url))
    for outcome in db.query(models.Outcome).order_by(models.Outcome.timestamp.desc()).limit(limit).all():
        test = db.query(models.Test).join(models.Decision, models.Decision.test_id == models.Test.id).filter(models.Decision.id == outcome.decision_id).first()
        if test:
            items.append(schemas.ActivityItem(kind="learning", title=f"Learned from {test.name}", detail=outcome.outcome.value, timestamp=outcome.timestamp, source="quarantineiq"))
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items[:limit]


@router.get("/decision-challenges")
def get_decision_challenges(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    rows = db.query(models.DecisionChallenge, models.Test.name).join(models.Test, models.DecisionChallenge.test_id == models.Test.id).order_by(models.DecisionChallenge.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id, "test_id": r.test_id, "test_name": name, "triggered": r.triggered,
            "reason": r.reason, "evidence_count": r.evidence_count, "created_at": r.created_at.isoformat(),
            "responded": r.responded, "response": r.response,
        }
        for r, name in rows
    ]


@router.get("/github/status")
def github_status(db: Session = Depends(get_db)):
    sync = db.query(models.RepositorySync).filter(models.RepositorySync.repository == GITHUB_REPOSITORY).first() if GITHUB_REPOSITORY else None
    connected = False
    if github_is_configured():
        try:
            from backend.github.client import GitHubClient
            GitHubClient().get_repo(GITHUB_REPOSITORY)
            connected = True
        except GitHubError:
            connected = False
    return {
        "configured": github_is_configured(),
        "connected": connected,
        "repository": GITHUB_REPOSITORY or None,
        "last_sync_at": sync.last_sync_at.isoformat() if sync and sync.last_sync_at else None,
        "last_status": sync.last_status if sync else "never_synced",
        "last_error": sync.last_error if sync else None,
    }


@router.post("/github/sync", response_model=schemas.GitHubSyncResponse)
def sync_github(db: Session = Depends(get_db)):
    if not github_is_configured():
        raise HTTPException(status_code=400, detail="GitHub is not configured. Set GITHUB_REPOSITORY=owner/repository.")
    try:
        return github_sync(db)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/github/webhook")
async def github_webhook(request: Request):
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="GITHUB_WEBHOOK_SECRET is not configured.")
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid GitHub webhook signature")
    event = request.headers.get("X-GitHub-Event", "")
    if event != "workflow_run":
        return {"accepted": False, "message": f"Ignored event: {event or 'unknown'}"}
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON webhook payload") from exc
    action = payload.get("action")
    repository = (payload.get("repository") or {}).get("full_name") or GITHUB_REPOSITORY
    run_id = (payload.get("workflow_run") or {}).get("id")
    if GITHUB_REPOSITORY and repository.lower() != GITHUB_REPOSITORY.lower():
        raise HTTPException(status_code=403, detail="Webhook repository does not match configured repository")
    if not run_id:
        return {"accepted": True, "processed": False, "message": "workflow_run.id missing"}
    external_id = f"workflow_run:{repository}:{run_id}:{action or 'unknown'}"

    db = SessionLocal()
    try:
        existing = db.query(models.IngestionEvent).filter(models.IngestionEvent.external_id == external_id).first()
        if existing:
            return {"accepted": True, "duplicate": True, "external_id": external_id}
        event_row = models.IngestionEvent(
            external_id=external_id,
            event_type=f"workflow_run.{action or 'unknown'}",
            repository=repository,
            status="received",
            received_at=datetime.utcnow(),
        )
        db.add(event_row)
        db.commit()
        if action != "completed":
            event_row.status = "ignored"
            event_row.processed_at = datetime.utcnow()
            db.commit()
            return {"accepted": True, "processed": False, "action": action}
        try:
            result = await _sync_run_async(repository, int(run_id))
            event_row.status = "processed"
            event_row.processed_at = datetime.utcnow()
            event_row.message = json.dumps(result)[:2000]
            db.commit()
            return {"accepted": True, "processed": True, "sync": result}
        except GitHubError as exc:
            event_row.status = "failed"
            event_row.processed_at = datetime.utcnow()
            event_row.message = str(exc)
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        db.close()


async def _sync_run_async(repository: str, run_id: int) -> dict:
    # GitHub REST calls are blocking stdlib calls; isolate them from the FastAPI event loop.
    import asyncio
    return await asyncio.to_thread(_sync_run_sync, repository, run_id)


def _sync_run_sync(repository: str, run_id: int) -> dict:
    db = SessionLocal()
    try:
        return github_sync(db, repository=repository, run_id=run_id)
    finally:
        db.close()


@router.post("/tests/{test_id}/investigate", response_model=schemas.InvestigateResponse)
async def investigate_test(test_id: int, db: Session = Depends(get_db)):
    current_evidence = _build_current_evidence(test_id, db)
    historical_evidence, memory_status = await _recall_for_evidence(current_evidence)
    result = intelligence_agent.investigate(current_evidence, historical_evidence)
    root_cause = analyze_root_cause(current_evidence, historical_evidence)
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    challenge = _challenge_for(test, historical_evidence, result["attention_score"]["score"])
    record = models.InvestigationRecord(
        test_id=test_id,
        score=result["attention_score"]["score"],
        recommendation=result["recommendation"]["level"],
        memory_status=memory_status,
        historical_count=len(historical_evidence),
        root_cause=root_cause["summary"],
        created_at=datetime.utcnow(),
    )
    db.add(record)
    if challenge["triggered"]:
        db.add(models.DecisionChallenge(test_id=test_id, triggered=True, reason=challenge["message"], evidence_count=challenge["evidence_count"], created_at=datetime.utcnow()))
    db.commit()
    return schemas.InvestigateResponse(
        current_evidence=current_evidence,
        historical_evidence=historical_evidence,
        attention_score=result["attention_score"],
        recommendation=result["recommendation"],
        reasoning_summary=result["reasoning_summary"],
        memory_status=memory_status,
        decision_challenge=challenge,
        root_cause=root_cause,
    )


class DecisionRequest(BaseModel):
    agent_recommendation: Optional[models.DecisionType] = None
    agent_reason: Optional[str] = None
    human_decision: models.DecisionType
    human_reason: str
    challenge_response: Optional[str] = None


@router.post("/tests/{test_id}/decision", response_model=schemas.Decision)
def create_decision(test_id: int, req: DecisionRequest, db: Session = Depends(get_db)):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if len(req.human_reason.strip()) < 3:
        raise HTTPException(status_code=422, detail="Human decision reason is required")
    agent_recommendation = req.agent_recommendation
    agent_reason = req.agent_reason
    latest = db.query(models.InvestigationRecord).filter(models.InvestigationRecord.test_id == test_id).order_by(models.InvestigationRecord.created_at.desc()).first()
    if agent_recommendation is None and latest:
        agent_recommendation = models.DecisionType.quarantine if latest.recommendation == "LOW" else models.DecisionType.investigate
    if not agent_reason and latest:
        agent_reason = latest.root_cause or "Recommendation based on the latest investigation evidence."
    if agent_recommendation is None or not agent_reason:
        raise HTTPException(status_code=400, detail="Investigate the test before recording a decision.")
    challenge = db.query(models.DecisionChallenge).filter(models.DecisionChallenge.test_id == test_id).order_by(models.DecisionChallenge.created_at.desc()).first()
    decision = models.Decision(
        test_id=test_id,
        agent_recommendation=agent_recommendation,
        agent_reason=agent_reason,
        human_decision=req.human_decision,
        human_reason=req.human_reason.strip(),
        timestamp=datetime.utcnow(),
        challenge_shown=bool(challenge and challenge.triggered),
        challenge_reason=challenge.reason if challenge and challenge.triggered else None,
    )
    db.add(decision)
    if challenge:
        challenge.responded = bool(req.challenge_response)
        challenge.response = req.challenge_response
    db.commit()
    db.refresh(decision)
    return decision


class OutcomeRequest(BaseModel):
    outcome: models.OutcomeType
    notes: str


async def _build_experience(test_id: int, outcome: models.Outcome, decision: models.Decision, db: Session) -> Dict[str, Any]:
    current_evidence = _build_current_evidence(test_id, db)
    latest_failure = next((run for run in current_evidence["history"] if run.get("status") == "failed"), None)
    return {
        "experience_id": f"quarantineiq:test:{test_id}:decision:{decision.id}:outcome:{outcome.id}",
        "memory_marker": f"quarantineiq-outcome-{outcome.id}",
        "test": current_evidence["test"]["name"],
        "service": current_evidence["test"]["service"],
        "repository": current_evidence["test"]["repository"],
        "failure_type": (latest_failure or {}).get("failure_type") or "unknown",
        "evidence": {
            "error_message": (latest_failure or {}).get("error_message"),
            "related_commits": current_evidence["related_commits"],
            "related_incidents": current_evidence["related_incidents"],
        },
        "decision": decision.agent_recommendation.value if decision.agent_recommendation else "unknown",
        "reason": decision.agent_reason or "unknown",
        "human_decision": decision.human_decision.value if decision.human_decision else "unknown",
        "outcome": outcome.outcome.value,
        "lesson": outcome.notes.strip(),
        "timestamp": outcome.timestamp.isoformat(),
    }


@router.post("/tests/{test_id}/outcome")
async def create_outcome(test_id: int, req: OutcomeRequest, db: Session = Depends(get_db)):
    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if len(req.notes.strip()) < 3:
        raise HTTPException(status_code=422, detail="Outcome notes are required")
    decision = db.query(models.Decision).filter(models.Decision.test_id == test_id).order_by(models.Decision.timestamp.desc()).first()
    if not decision:
        raise HTTPException(status_code=400, detail="No decision found for this test")
    outcome = models.Outcome(decision_id=decision.id, outcome=req.outcome, notes=req.notes.strip(), timestamp=datetime.utcnow())
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    experience = await _build_experience(test_id, outcome, decision, db)
    try:
        retained = await hindsight_client.async_retain_experience(experience)
        memory_status = "retained"
    except hindsight_client.HindsightError as exc:
        retained = False
        memory_status = f"unavailable: {exc}"
    return {
        "outcome": schemas.Outcome.model_validate(outcome),
        "memory_retained": retained,
        "memory_status": memory_status,
        "experience": experience,
    }


@router.post("/tests/{test_id}/outcome/{outcome_id}/teach")
async def teach_outcome(test_id: int, outcome_id: int, db: Session = Depends(get_db)):
    outcome = db.query(models.Outcome).filter(models.Outcome.id == outcome_id).first()
    if not outcome or outcome.decision.test_id != test_id:
        raise HTTPException(status_code=404, detail="Outcome not found")
    experience = await _build_experience(test_id, outcome, outcome.decision, db)
    try:
        retained = await hindsight_client.async_retain_experience(experience)
        return {"memory_retained": retained, "memory_status": "retained", "experience": experience}
    except hindsight_client.HindsightError as exc:
        return {"memory_retained": False, "memory_status": f"unavailable: {exc}", "experience": experience}


@router.post("/demo/without-memory", response_model=schemas.InvestigateResponse)
def demo_without_memory(db: Session = Depends(get_db)):
    test = db.query(models.Test).filter(models.Test.name == "test_payment_timeout").first()
    if not test:
        raise HTTPException(status_code=404, detail="Demo test data not loaded")
    current = _build_current_evidence(test.id, db)
    result = intelligence_agent.investigate(current, [])
    root_cause = analyze_root_cause(current, [])
    return schemas.InvestigateResponse(current_evidence=current, historical_evidence=[], attention_score=result["attention_score"], recommendation=result["recommendation"], reasoning_summary=result["reasoning_summary"], memory_status="disabled for demo", decision_challenge={"triggered": False, "message": None, "evidence_count": 0}, root_cause=root_cause)


@router.post("/demo/with-memory", response_model=schemas.InvestigateResponse)
async def demo_with_memory(db: Session = Depends(get_db)):
    test = db.query(models.Test).filter(models.Test.name == "test_payment_timeout").first()
    if not test:
        raise HTTPException(status_code=404, detail="Demo test data not loaded")
    current = _build_current_evidence(test.id, db)
    historical, status = await _recall_for_evidence(current, limit=10)
    result = intelligence_agent.investigate(current, historical)
    root_cause = analyze_root_cause(current, historical)
    challenge = _challenge_for(test, historical, result["attention_score"]["score"])
    return schemas.InvestigateResponse(current_evidence=current, historical_evidence=historical, attention_score=result["attention_score"], recommendation=result["recommendation"], reasoning_summary=result["reasoning_summary"], memory_status=status, decision_challenge=challenge, root_cause=root_cause)


@router.post("/demo/compare")
async def demo_compare(db: Session = Depends(get_db)):
    without = demo_without_memory(db)
    with_memory = await demo_with_memory(db)
    return {"without_memory": without.model_dump(), "with_memory": with_memory.model_dump()}


@router.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db)):
    # Resetting demo data is intentionally separate from Hindsight. Seed script can re-use existing stable memory markers.
    from pathlib import Path
    import runpy
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "seed_demo.py"
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "Demo data reset successfully"}


@router.get("/demo/status")
def get_demo_status(db: Session = Depends(get_db)):
    test_count = db.query(models.Test).count()
    payment = db.query(models.Test).filter(models.Test.name == "test_payment_timeout").first()
    return {"loaded": test_count > 0, "test_count": test_count, "payment_demo_loaded": payment is not None}
