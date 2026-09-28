import io
import json
import os
import re
import zipfile
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

GITHUB_API = os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip("/")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "").strip()
GITHUB_DEFAULT_BRANCH = os.getenv("GITHUB_DEFAULT_BRANCH", "main").strip() or "main"
GITHUB_API_VERSION = os.getenv("GITHUB_API_VERSION", "2026-03-10").strip()


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(self, token: str = GITHUB_TOKEN):
        self.token = token.strip()

    def _request(self, path: str, accept: str = "application/vnd.github+json", timeout: int = 20) -> Any:
        headers = {
            "Accept": accept,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "QuarantineIQ-V3",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(f"{GITHUB_API}{path}", headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                ctype = response.headers.get("Content-Type", "")
                if "json" in ctype or raw[:1] in (b"{", b"["):
                    return json.loads(raw.decode("utf-8"))
                return raw
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1500]
            if exc.code == 401:
                raise GitHubError("GitHub authentication failed. Check GITHUB_TOKEN.") from exc
            if exc.code == 403 and "rate limit" in body.lower():
                raise GitHubError("GitHub API rate limit reached. Configure a token or wait for reset.") from exc
            if exc.code == 404:
                raise GitHubError("GitHub repository or resource not found. Check GITHUB_REPOSITORY and token access.") from exc
            raise GitHubError(f"GitHub API {exc.code}: {body}") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise GitHubError(f"GitHub connection failed: {exc}") from exc

    def get_repo(self, repository: str = GITHUB_REPOSITORY) -> Dict[str, Any]:
        owner, repo = split_repository(repository)
        return self._request(f"/repos/{owner}/{repo}")

    def list_workflows(self, repository: str = GITHUB_REPOSITORY) -> List[Dict[str, Any]]:
        owner, repo = split_repository(repository)
        data = self._request(f"/repos/{owner}/{repo}/actions/workflows?per_page=100")
        return data.get("workflows", []) if isinstance(data, dict) else []

    def list_workflow_runs(self, repository: str = GITHUB_REPOSITORY, per_page: int = 50) -> List[Dict[str, Any]]:
        owner, repo = split_repository(repository)
        data = self._request(f"/repos/{owner}/{repo}/actions/runs?per_page={min(per_page, 100)}")
        return data.get("workflow_runs", []) if isinstance(data, dict) else []

    def get_workflow_run(self, repository: str, run_id: int) -> Dict[str, Any]:
        owner, repo = split_repository(repository)
        return self._request(f"/repos/{owner}/{repo}/actions/runs/{run_id}")

    def list_jobs(self, repository: str, run_id: int) -> List[Dict[str, Any]]:
        owner, repo = split_repository(repository)
        data = self._request(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?per_page=100&filter=latest")
        return data.get("jobs", []) if isinstance(data, dict) else []

    def get_job(self, repository: str, job_id: int) -> Dict[str, Any]:
        owner, repo = split_repository(repository)
        return self._request(f"/repos/{owner}/{repo}/actions/jobs/{job_id}")

    def get_job_logs(self, repository: str, job_id: int) -> str:
        owner, repo = split_repository(repository)
        raw = self._request(f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs", timeout=30)
        if isinstance(raw, bytes):
            return decode_logs(raw)
        return str(raw)[:50000]

    def get_commit(self, repository: str, sha: str) -> Dict[str, Any]:
        owner, repo = split_repository(repository)
        return self._request(f"/repos/{owner}/{repo}/commits/{sha}")

    def list_commits(self, repository: str = GITHUB_REPOSITORY, per_page: int = 20) -> List[Dict[str, Any]]:
        owner, repo = split_repository(repository)
        data = self._request(f"/repos/{owner}/{repo}/commits?per_page={min(per_page, 100)}")
        return data if isinstance(data, list) else []


def split_repository(repository: str) -> tuple[str, str]:
    value = repository.strip().removeprefix("https://github.com/").removeprefix("http://github.com/").rstrip("/")
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise GitHubError("GITHUB_REPOSITORY must use owner/repository format.")
    return parts[0], parts[1]


def decode_logs(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            parts = []
            for name in archive.namelist()[:50]:
                info = archive.getinfo(name)
                if info.file_size > 2_000_000:
                    continue
                parts.append(f"--- {name} ---\n{archive.read(name).decode('utf-8', errors='replace')}")
            return "\n".join(parts)[-50000:]
    except zipfile.BadZipFile:
        return raw.decode("utf-8", errors="replace")[-50000:]


def extract_test_names(log_text: str, job_name: str) -> List[str]:
    names: List[str] = []
    patterns = [
        r"FAILED\s+([^\s:]+(?:::[^\s]+)*)",
        r"(?:FAIL|FAILURE)\s+([A-Za-z0-9_./:-]+)",
        r"\btest_[A-Za-z0-9_./:-]+\b",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, log_text or "", flags=re.I):
            value = match if isinstance(match, str) else match[0]
            if value and value not in names:
                names.append(value.strip())
    if not names and job_name:
        names.append(normalize_job_name(job_name))
    return names[:10]


def normalize_job_name(job_name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", job_name.strip().lower()).strip("_")
    return f"github_{value or 'ci_job'}"
