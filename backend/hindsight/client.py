import atexit
import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

try:
    from hindsight_client import Hindsight
except ImportError:  # pragma: no cover
    Hindsight = None

logger = logging.getLogger(__name__)
HINDSIGHT_URL = os.getenv("HINDSIGHT_URL", "http://localhost:8888").rstrip("/")
HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY", "").strip()
HINDSIGHT_BANK_ID = os.getenv("HINDSIGHT_BANK_ID", "quarantineiq-experiences").strip() or "quarantineiq-experiences"
DEFAULT_TIMEOUT = float(os.getenv("HINDSIGHT_CLIENT_TIMEOUT", "45"))


class HindsightError(RuntimeError):
    """Application-level error for Hindsight operations."""


def hindsight_health(timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(f"{HINDSIGHT_URL}/health", timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") == "healthy"
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return False


async def async_hindsight_health(timeout: float = 3.0) -> bool:
    return await asyncio.to_thread(hindsight_health, timeout)


def _build_client():
    if Hindsight is None:
        raise HindsightError("The hindsight-client package is not installed.")
    kwargs = {"base_url": HINDSIGHT_URL, "timeout": DEFAULT_TIMEOUT}
    if HINDSIGHT_API_KEY:
        kwargs["api_key"] = HINDSIGHT_API_KEY
    try:
        return Hindsight(**kwargs)
    except TypeError:
        kwargs.pop("timeout", None)
        return Hindsight(**kwargs)


async def _close_async_client(client: Any) -> None:
    closer = getattr(client, "aclose", None)
    if callable(closer):
        result = closer()
        if inspect_is_awaitable(result):
            await result
        return
    closer = getattr(client, "close", None)
    if callable(closer):
        result = closer()
        if inspect_is_awaitable(result):
            await result


def inspect_is_awaitable(value: Any) -> bool:
    return hasattr(value, "__await__")


async def async_retain_experience(experience: Dict[str, Any]) -> bool:
    if not await async_hindsight_health():
        raise HindsightError(f"Hindsight is unavailable at {HINDSIGHT_URL}.")

    client = _build_client()
    content = json.dumps(experience, ensure_ascii=False, default=str)
    document_id = str(experience.get("experience_id") or experience.get("memory_marker") or "quarantineiq-experience")
    context = "QuarantineIQ engineering decision and outcome memory."
    metadata = {
        key: str(value)
        for key, value in {
            "source": "quarantineiq",
            "test": experience.get("test"),
            "service": experience.get("service"),
            "outcome": experience.get("outcome"),
            "memory_marker": experience.get("memory_marker"),
        }.items()
        if value is not None
    }
    try:
        response = await client.aretain(
            bank_id=HINDSIGHT_BANK_ID,
            content=content,
            context=context,
            document_id=document_id,
            metadata=metadata,
        )
        if hasattr(response, "success"):
            return bool(response.success)
        return True
    except Exception as exc:
        logger.exception("Hindsight async retain failed")
        raise HindsightError(str(exc)) from exc
    finally:
        try:
            await _close_async_client(client)
        except Exception:
            logger.debug("Failed to close Hindsight async client", exc_info=True)


def _extract_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return result.get("text") or result.get("content") or result.get("raw_content") or ""
    return getattr(result, "text", None) or getattr(result, "content", None) or getattr(result, "raw_content", None) or ""


def _extract_score(result: Any) -> Optional[float]:
    value = result.get("score") if isinstance(result, dict) else getattr(result, "score", None)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_recall_result(result: Any) -> Optional[Dict[str, Any]]:
    text = _extract_text(result)
    if not text:
        return None
    try:
        parsed = json.loads(text)
        payload = parsed if isinstance(parsed, dict) else {"raw_content": text}
    except (json.JSONDecodeError, TypeError):
        payload = {"raw_content": text}
    score = _extract_score(result)
    if score is not None:
        payload["_score"] = score
    return payload


async def async_recall_experiences(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    if not await async_hindsight_health():
        raise HindsightError(f"Hindsight is unavailable at {HINDSIGHT_URL}.")

    client = _build_client()
    try:
        response = await client.arecall(
            bank_id=HINDSIGHT_BANK_ID,
            query=query,
            limit=limit,
        )
        results = getattr(response, "results", None)
        if results is None and isinstance(response, list):
            results = response
        if results is None and isinstance(response, dict):
            results = response.get("results", response.get("memories", []))
        output: List[Dict[str, Any]] = []
        for result in list(results or []):
            parsed = _parse_recall_result(result)
            if parsed:
                output.append(parsed)
            if len(output) >= limit:
                break
        return output
    except Exception as exc:
        logger.exception("Hindsight async recall failed")
        raise HindsightError(str(exc)) from exc
    finally:
        try:
            await _close_async_client(client)
        except Exception:
            logger.debug("Failed to close Hindsight async client", exc_info=True)


def retain_experience(experience: Dict[str, Any]) -> bool:
    try:
        return asyncio.run(async_retain_experience(experience))
    except RuntimeError:
        raise HindsightError("retain_experience() is a sync helper; use async_retain_experience() inside FastAPI.")


def recall_experiences(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    try:
        return asyncio.run(async_recall_experiences(query, limit))
    except RuntimeError:
        raise HindsightError("recall_experiences() is a sync helper; use async_recall_experiences() inside FastAPI.")


def async_reflect_experience(query: str, context: Optional[str] = None) -> str:
    return ""


async def async_reflect(query: str, context: Optional[str] = None) -> str:
    if not await async_hindsight_health():
        raise HindsightError(f"Hindsight is unavailable at {HINDSIGHT_URL}.")
    client = _build_client()
    try:
        kwargs = {"bank_id": HINDSIGHT_BANK_ID, "query": query}
        if context:
            kwargs["context"] = context
        response = await client.areflect(**kwargs)
        return getattr(response, "text", "") or ""
    except Exception as exc:
        logger.exception("Hindsight async reflect failed")
        raise HindsightError(str(exc)) from exc
    finally:
        try:
            await _close_async_client(client)
        except Exception:
            logger.debug("Failed to close Hindsight async client", exc_info=True)
