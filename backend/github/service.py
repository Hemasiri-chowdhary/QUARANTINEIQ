from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database import models
from .client import (
    GITHUB_REPOSITORY,
    GitHubClient,
    GitHubError,
    extract_test_names,
    split_repository,
)


def github_is_configured() -> bool:
    return bool(GITHUB_REPOSITORY)


def _dt(value: Optional[str]) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.utcnow()


def _duration_ms(run: dict, job: dict) -> int:
    start = job.get("started_at") or run.get("run_started_at") or run.get("created_at")
    end = job.get("completed_at") or run.get("updated_at") or run.get("created_at")
    if start and end:
        return max(0, int((_dt(end) - _dt(start)).total_seconds() * 1000))
    return 0


def _failure_type(job: dict, logs: str) -> str:
    text = f"{job.get('conclusion', '')} {logs}".lower()
    checks = [
        ("timeout", "timeout"),
        ("timed out", "timeout"),
        ("429", "rate_limit"),
        ("503", "dependency_503"),
        ("connection", "connection"),
        ("assert", "assertion"),
        ("permission", "authorization"),
        ("unauthorized", "authorization"),
        ("not found", "missing_resource"),
    ]
    for key, label in checks:
        if key in text:
            return label
    return "ci_failure" if job.get("conclusion") in {"failure", "timed_out"} else "unknown"


def _error_message(logs: str) -> Optional[str]:
    lines = [line.strip() for line in (logs or "").splitlines() if line.strip()]
    for line in reversed(lines):
        lower = line.lower()
        if any(token in lower for token in ("error", "failed", "failure", "exception", "timeout")):
            return line[:800]
    return lines[-1][:800] if lines else None


def _upsert_commit(db: Session, client: GitHubClient, repository: str, sha: str, cache: Dict[str, dict]) -> tuple[Optional[models.Commit], bool]:
    if not sha:
        return None, False
    existing = db.query(models.Commit).filter(models.Commit.sha == sha).first()
    if existing:
        return existing, False
    try:
        data = cache.get(sha) or client.get_commit(repository, sha)
        cache[sha] = data
    except GitHubError:
        return None, False
    message = ((data.get("commit") or {}).get("message") or "").splitlines()[0][:500]
    author = ((data.get("author") or {}).get("login") or ((data.get("commit") or {}).get("author") or {}).get("name") or "unknown")
    files = ",".join(f.get("filename", "") for f in (data.get("files") or [])[:60])
    commit = models.Commit(
        sha=sha,
        message=message,
        files_changed=files,
        author=author,
        timestamp=_dt((data.get("commit") or {}).get("author", {}).get("date")),
        repository=repository,
        url=data.get("html_url"),
        source="github",
    )
    db.add(commit)
    db.flush()
    return commit, True


def _process_job(db: Session, client: GitHubClient, repository: str, run: dict, job: dict, commit_cache: Dict[str, dict]) -> tuple[int, int, int]:
    job_id = str(job.get("id") or "")
    if not job_id:
        return 0, 0, 0
    if db.query(models.CIRun).filter(models.CIRun.job_id == job_id).first():
        return 0, 0, 0

    conclusion = str(job.get("conclusion") or "").lower()
    status = "passed" if conclusion == "success" else "failed" if conclusion in {"failure", "timed_out"} else conclusion or str(job.get("status") or "unknown")
    logs = ""
    if status == "failed":
        try:
            logs = client.get_job_logs(repository, int(job_id))
        except GitHubError:
            logs = ""

    test_names = extract_test_names(logs, job.get("name") or run.get("name") or "ci-job")
    test_name = test_names[0] if test_names else "github_ci_job"
    owner, repo = split_repository(repository)
    del owner
    external_key = f"github:{repository}:{test_name}"
    test = db.query(models.Test).filter(models.Test.external_key == external_key).first()
    if not test:
        test = models.Test(
            name=test_name,
            service=f"github/{repo}",
            repository=repository,
            status=models.TestStatus.needs_review if status == "failed" else models.TestStatus.active,
            created_at=_dt(run.get("created_at")),
            source="github",
            external_key=external_key,
        )
        db.add(test)
        db.flush()
        created_test = 1
    else:
        created_test = 0
        if status == "failed" and test.status == models.TestStatus.active:
            test.status = models.TestStatus.needs_review

    sha = run.get("head_sha") or job.get("head_sha") or ""
    commit, commit_created = _upsert_commit(db, client, repository, sha, commit_cache)
    created_commit = 1 if commit_created else 0
    run_obj = models.CIRun(
        test_id=test.id,
        commit_sha=sha or "unknown",
        status=status,
        failure_type=_failure_type(job, logs) if status == "failed" else None,
        error_message=_error_message(logs) if status == "failed" else None,
        duration=_duration_ms(run, job),
        retry_count=max(0, int(run.get("run_attempt") or 1) - 1),
        retry_success=False,
        timestamp=_dt(job.get("completed_at") or run.get("updated_at") or run.get("created_at")),
        source="github",
        workflow_run_id=str(run.get("id") or ""),
        job_id=job_id,
        workflow_name=run.get("name"),
        job_name=job.get("name"),
        log_excerpt=logs[-12000:] if logs else None,
        html_url=run.get("html_url") or job.get("html_url"),
        branch=(run.get("head_branch") or "").strip() or None,
        run_attempt=int(run.get("run_attempt") or 1),
    )
    db.add(run_obj)
    return created_test, 1, created_commit


def github_sync(db: Session, repository: Optional[str] = None, run_id: Optional[int] = None) -> dict:
    repository = (repository or GITHUB_REPOSITORY).strip()
    if not repository:
        raise GitHubError("No GitHub repository configured. Set GITHUB_REPOSITORY=owner/repo.")
    client = GitHubClient()
    client.get_repo(repository)
    runs = [client.get_workflow_run(repository, run_id)] if run_id else client.list_workflow_runs(repository, per_page=50)

    sync = db.query(models.RepositorySync).filter(models.RepositorySync.repository == repository).first()
    if not sync:
        sync = models.RepositorySync(repository=repository, source="github")
        db.add(sync)
        db.flush()

    created_tests = created_runs = created_commits = jobs_seen = 0
    errors: List[str] = []
    commit_cache: Dict[str, dict] = {}

    for run in runs:
        current_run_id = str(run.get("id") or "")
        if not current_run_id:
            continue
        try:
            jobs = client.list_jobs(repository, int(current_run_id))
        except GitHubError as exc:
            errors.append(f"run {current_run_id}: {exc}")
            continue
        jobs_seen += len(jobs)
        for job in jobs:
            try:
                t, r, c = _process_job(db, client, repository, run, job, commit_cache)
                created_tests += t
                created_runs += r
                created_commits += c
            except Exception as exc:
                errors.append(f"job {job.get('id', 'unknown')}: {exc}")

    # Make GitHub's actual repository default branch authoritative when available.
    try:
        repo_info = client.get_repo(repository)
        default_branch = repo_info.get("default_branch")
        if default_branch:
            from backend.github import client as gh_client_module
            gh_client_module.GITHUB_DEFAULT_BRANCH = default_branch
    except Exception:
        pass

    sync.last_sync_at = datetime.utcnow()
    sync.last_status = "success" if not errors else "partial"
    sync.last_error = " | ".join(errors[:10]) if errors else None
    sync.workflows_seen = len(runs)
    sync.jobs_seen = jobs_seen
    db.commit()
    return {
        "repository": repository,
        "status": sync.last_status,
        "workflows_seen": len(runs),
        "jobs_seen": jobs_seen,
        "tests_created": created_tests,
        "runs_created": created_runs,
        "commits_created": created_commits,
        "errors": errors[:20],
    }
