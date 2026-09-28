from datetime import datetime
import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.database.session import Base


class TestStatus(str, enum.Enum):
    active = "active"
    quarantined = "quarantined"
    disabled = "disabled"
    needs_review = "needs_review"


class DecisionType(str, enum.Enum):
    quarantine = "quarantine"
    investigate = "investigate"
    keep_active = "keep_active"


class OutcomeType(str, enum.Enum):
    genuinely_flaky = "genuinely_flaky"
    infrastructure_issue = "infrastructure_issue"
    real_regression = "real_regression"
    still_uncertain = "still_uncertain"


class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    service = Column(String, index=True)
    repository = Column(String)
    status = Column(Enum(TestStatus), default=TestStatus.active)
    created_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="demo")
    external_key = Column(String, unique=True, nullable=True, index=True)

    ci_runs = relationship("CIRun", back_populates="test", cascade="all, delete-orphan")
    decisions = relationship("Decision", back_populates="test", cascade="all, delete-orphan")


class CIRun(Base):
    __tablename__ = "ci_runs"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"))
    commit_sha = Column(String)
    status = Column(String)
    failure_type = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    duration = Column(Integer)
    retry_count = Column(Integer, default=0)
    retry_success = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="demo")
    workflow_run_id = Column(String, nullable=True, index=True)
    job_id = Column(String, nullable=True, index=True)
    workflow_name = Column(String, nullable=True)
    job_name = Column(String, nullable=True)
    log_excerpt = Column(Text, nullable=True)
    html_url = Column(String, nullable=True)
    branch = Column(String, nullable=True)
    run_attempt = Column(Integer, default=1)

    test = relationship("Test", back_populates="ci_runs")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"))
    agent_recommendation = Column(Enum(DecisionType), nullable=True)
    agent_reason = Column(Text, nullable=True)
    human_decision = Column(Enum(DecisionType), nullable=True)
    human_reason = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    challenge_shown = Column(Boolean, default=False)
    challenge_reason = Column(Text, nullable=True)

    test = relationship("Test", back_populates="decisions")
    outcomes = relationship("Outcome", back_populates="decision", cascade="all, delete-orphan")


class Outcome(Base):
    __tablename__ = "outcomes"

    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"))
    outcome = Column(Enum(OutcomeType))
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    decision = relationship("Decision", back_populates="outcomes")


class Commit(Base):
    __tablename__ = "commits"

    id = Column(Integer, primary_key=True, index=True)
    sha = Column(String, unique=True, index=True)
    message = Column(String)
    files_changed = Column(String)
    author = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    repository = Column(String, nullable=True)
    url = Column(String, nullable=True)
    source = Column(String, default="demo")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    service = Column(String, index=True)
    title = Column(String)
    description = Column(Text)
    root_cause = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    source = Column(String, default="demo")


class InvestigationRecord(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"))
    score = Column(Integer, default=0)
    recommendation = Column(String)
    memory_status = Column(String)
    historical_count = Column(Integer, default=0)
    root_cause = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    test = relationship("Test")


class IngestionEvent(Base):
    __tablename__ = "ingestion_events"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True)
    event_type = Column(String)
    repository = Column(String)
    status = Column(String, default="received")
    received_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    message = Column(Text, nullable=True)


class DecisionChallenge(Base):
    __tablename__ = "decision_challenges"

    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.id"))
    triggered = Column(Boolean, default=False)
    reason = Column(Text, nullable=True)
    evidence_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    responded = Column(Boolean, default=False)
    response = Column(String, nullable=True)

    test = relationship("Test")


class RepositorySync(Base):
    __tablename__ = "repository_syncs"

    id = Column(Integer, primary_key=True, index=True)
    repository = Column(String, unique=True, index=True)
    last_sync_at = Column(DateTime, nullable=True)
    last_status = Column(String, default="never_synced")
    last_error = Column(Text, nullable=True)
    workflows_seen = Column(Integer, default=0)
    jobs_seen = Column(Integer, default=0)
    source = Column(String, default="github")
