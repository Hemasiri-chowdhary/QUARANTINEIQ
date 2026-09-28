from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.database.models import DecisionType, OutcomeType, TestStatus


class CIRunBase(BaseModel):
    commit_sha: str
    status: str
    failure_type: Optional[str] = None
    error_message: Optional[str] = None
    duration: int
    retry_count: int = 0
    retry_success: bool = False
    timestamp: datetime
    source: str = "demo"
    workflow_run_id: Optional[str] = None
    job_id: Optional[str] = None
    workflow_name: Optional[str] = None
    job_name: Optional[str] = None
    log_excerpt: Optional[str] = None
    html_url: Optional[str] = None
    branch: Optional[str] = None
    run_attempt: int = 1


class CIRun(CIRunBase):
    id: int
    test_id: int
    model_config = ConfigDict(from_attributes=True)


class OutcomeBase(BaseModel):
    outcome: OutcomeType
    notes: Optional[str] = None
    timestamp: datetime


class Outcome(OutcomeBase):
    id: int
    decision_id: int
    model_config = ConfigDict(from_attributes=True)


class DecisionBase(BaseModel):
    agent_recommendation: Optional[DecisionType] = None
    agent_reason: Optional[str] = None
    human_decision: Optional[DecisionType] = None
    human_reason: Optional[str] = None
    timestamp: datetime
    challenge_shown: bool = False
    challenge_reason: Optional[str] = None


class Decision(DecisionBase):
    id: int
    test_id: int
    model_config = ConfigDict(from_attributes=True)


class TestBase(BaseModel):
    name: str
    service: str
    repository: str
    status: TestStatus
    created_at: datetime
    source: str = "demo"
    external_key: Optional[str] = None


class Test(TestBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class MemoryItem(BaseModel):
    test: Optional[str] = None
    service: Optional[str] = None
    repository: Optional[str] = None
    failure_type: Optional[str] = None
    decision: Optional[str] = None
    human_decision: Optional[str] = None
    outcome: Optional[str] = None
    lesson: Optional[str] = None
    timestamp: Optional[str] = None
    evidence: Any = None
    raw_content: Optional[str] = None
    memory_marker: Optional[str] = None
    source_count: int = 1
    relevance_score: Optional[int] = None


class RootCauseSignal(BaseModel):
    signal: str
    evidence: str
    strength: str


class RootCauseAnalysis(BaseModel):
    summary: str
    signals: List[RootCauseSignal] = Field(default_factory=list)
    caveat: str


class InvestigateResponse(BaseModel):
    current_evidence: Dict[str, Any]
    historical_evidence: List[Dict[str, Any]]
    attention_score: Dict[str, Any]
    recommendation: Dict[str, Any]
    reasoning_summary: str
    memory_status: str
    decision_challenge: Dict[str, Any]
    root_cause: Optional[RootCauseAnalysis] = None


class GitHubSyncResponse(BaseModel):
    repository: str
    status: str
    workflows_seen: int = 0
    jobs_seen: int = 0
    tests_created: int = 0
    runs_created: int = 0
    commits_created: int = 0
    errors: List[str] = Field(default_factory=list)


class Pattern(BaseModel):
    pattern: str
    description: str
    count: int
    affected_tests: List[str] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    real_regression_count: int = 0
    examples: List[Dict[str, Any]] = Field(default_factory=list)
    signal_strength: Optional[str] = None


class ActivityItem(BaseModel):
    kind: str
    title: str
    detail: str
    timestamp: datetime
    source: str = "demo"
    url: Optional[str] = None


class RepositoryStatus(BaseModel):
    configured: bool
    repository: Optional[str] = None
    connected: bool
    last_sync_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
