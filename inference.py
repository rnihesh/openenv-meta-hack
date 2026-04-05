"""Baseline inference script for ticket_triage_env.

Required environment variables:
  API_BASE_URL   The LLM API endpoint.
  MODEL_NAME     The model identifier.
  HF_TOKEN       Your Hugging Face / API key.

Optional:
  ENV_BASE_URL           URL of the running environment server (default: http://localhost:8000)
  IMAGE_NAME             Docker image name (default: ticket-triage-env:latest)
  MAX_STEPS              Max steps per task episode (default: 8)
  SUCCESS_SCORE_THRESHOLD  Score threshold for success (default: 0.75)
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from openai import OpenAI

BENCHMARK = "ticket_triage_env"
API_BASE_URL = os.getenv("API_BASE_URL", "").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "").strip()
API_KEY = (os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY") or "").strip()
ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000").rstrip("/")
IMAGE_NAME = os.getenv("IMAGE_NAME", "ticket-triage-env:latest").strip()
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
SUCCESS_SCORE_THRESHOLD = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.75"))

VALID_CATEGORIES = ["billing", "technical", "account", "abuse", "shipping"]
VALID_PRIORITIES = ["low", "medium", "high", "urgent"]
VALID_TEAMS = [
    "billing_ops",
    "tech_support",
    "account_services",
    "trust_safety",
    "fulfillment",
]
TASK_IDS = ["easy", "medium", "hard"]


# ---------------------------------------------------------------------------
# Structured logging (required format)
# ---------------------------------------------------------------------------

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] {json.dumps({'task': task, 'env': env, 'model': model}, ensure_ascii=True)}", flush=True)


def log_step(step: int, action: Dict[str, Any], reward: float, done: bool, error: Optional[str]) -> None:
    payload = {
        "step": step,
        "action": action,
        "reward": round(float(reward), 6),
        "done": bool(done),
        "error": error,
    }
    print(f"[STEP] {json.dumps(payload, ensure_ascii=True)}", flush=True)


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    payload = {
        "success": bool(success),
        "steps": int(steps),
        "score": round(float(score), 6),
        "rewards": [round(float(r), 6) for r in rewards],
    }
    print(f"[END] {json.dumps(payload, ensure_ascii=True)}", flush=True)


# ---------------------------------------------------------------------------
# Environment HTTP client
# ---------------------------------------------------------------------------

class EnvHTTPClient:
    """Thin async HTTP wrapper around the OpenEnv server."""

    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)
        self._session_id: Optional[str] = None

    async def reset(self, task_id: str) -> Dict[str, Any]:
        resp = await self._client.post(
            f"{self._base}/reset",
            json={"task_id": task_id},
        )
        resp.raise_for_status()
        data = resp.json()
        self._session_id = data.get("session_id") or data.get("episode_id")
        return data

    async def step(self, action: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"action": action}
        if self._session_id:
            payload["request_id"] = self._session_id
        resp = await self._client.post(f"{self._base}/step", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize(value: Any, allowed: List[str], default: str) -> str:
    if isinstance(value, str) and value.strip().lower() in allowed:
        return value.strip().lower()
    return default


# ---------------------------------------------------------------------------
# Heuristic fallback policy
# ---------------------------------------------------------------------------

def heuristic_action(obs: Dict[str, Any]) -> Dict[str, Any]:
    pending = obs.get("pending_ticket_ids", [])
    tickets = {t["ticket_id"]: t for t in obs.get("tickets", [])}

    if not pending:
        triaged = obs.get("triaged_ticket_ids", [])
        return {
            "ticket_id": triaged[-1] if triaged else "",
            "predicted_category": "technical",
            "predicted_priority": "low",
            "assigned_team": "tech_support",
            "resolution_summary": "No pending tickets. Finalizing.",
            "finalize": True,
        }

    ticket_id = pending[0]
    ticket = tickets.get(ticket_id, {})
    message = ticket.get("customer_message", "").lower()

    if any(t in message for t in ["refund", "charged", "invoice", "payment"]):
        category = "billing"
    elif any(t in message for t in ["harass", "abuse", "threat", "suspicious", "take over"]):
        category = "abuse"
    elif any(t in message for t in ["address", "shipment", "order", "dispatch"]):
        category = "shipping"
    elif any(t in message for t in ["password", "login", "2fa", "account", "api key"]):
        category = "account"
    else:
        category = "technical"

    if any(t in message for t in ["urgent", "immediate", "now", "deadline", "harass", "take over"]):
        priority = "urgent"
    elif any(t in message for t in ["blocked", "crash", "charged twice", "legal"]):
        priority = "high"
    elif any(t in message for t in ["today", "tomorrow", "before"]):
        priority = "medium"
    else:
        priority = "low"

    team_map = {
        "billing": "billing_ops",
        "technical": "tech_support",
        "shipping": "fulfillment",
        "abuse": "trust_safety",
        "account": "account_services",
    }
    team = team_map.get(category, "tech_support")
    if category == "account" and any(t in message for t in ["suspicious", "take over", "api key"]):
        team = "trust_safety"

    summary_map = {
        "billing": "invoice refund deadline",
        "abuse": "escalate evidence secure",
        "technical": "reproduce logs audit",
        "shipping": "address shipment confirm",
        "account": "reset verification investigate",
    }
    summary = summary_map.get(category, "review customer follow-up")
    finalize = len(pending) == 1

    return {
        "ticket_id": ticket_id,
        "predicted_category": category,
        "predicted_priority": priority,
        "assigned_team": team,
        "resolution_summary": summary,
        "finalize": finalize,
    }


# ---------------------------------------------------------------------------
# Model action
# ---------------------------------------------------------------------------

def get_model_action(
    client: Optional[OpenAI],
    obs: Dict[str, Any],
    history: List[str],
) -> Dict[str, Any]:
    fallback = heuristic_action(obs)
    if client is None:
        return fallback

    prompt = {
        "task_id": obs.get("task_id"),
        "objective": obs.get("objective"),
        "pending_ticket_ids": obs.get("pending_ticket_ids", []),
        "tickets": obs.get("tickets", []),
        "history": history[-8:],
        "required_output": {
            "ticket_id": "string",
            "predicted_category": VALID_CATEGORIES,
            "predicted_priority": VALID_PRIORITIES,
            "assigned_team": VALID_TEAMS,
            "resolution_summary": "short string",
            "finalize": "boolean",
        },
    }

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a support operations assistant. "
                        "Return exactly one JSON object with the requested fields and no markdown."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=True)},
            ],
        )
        payload = _extract_json(response.choices[0].message.content or "")
        if payload is None:
            return fallback

        return {
            "ticket_id": str(payload.get("ticket_id", fallback["ticket_id"])),
            "predicted_category": _normalize(
                payload.get("predicted_category"), VALID_CATEGORIES, fallback["predicted_category"]
            ),
            "predicted_priority": _normalize(
                payload.get("predicted_priority"), VALID_PRIORITIES, fallback["predicted_priority"]
            ),
            "assigned_team": _normalize(
                payload.get("assigned_team"), VALID_TEAMS, fallback["assigned_team"]
            ),
            "resolution_summary": str(payload.get("resolution_summary", fallback["resolution_summary"]))[:500],
            "finalize": bool(payload.get("finalize", fallback["finalize"])),
        }
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return fallback


# ---------------------------------------------------------------------------
# Task runner
# ---------------------------------------------------------------------------

async def run_task(env: EnvHTTPClient, client: Optional[OpenAI], task_id: str) -> float:
    rewards: List[float] = []
    history: List[str] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    result = await env.reset(task_id=task_id)
    obs = result.get("observation", result)

    for step in range(1, MAX_STEPS + 1):
        if result.get("done", False):
            break

        action = get_model_action(client, obs, history)
        error: Optional[str] = None

        try:
            result = await env.step(action)
            obs = result.get("observation", result)
            reward = float(result.get("reward") or 0.0)
            done = bool(result.get("done", False))
        except Exception as exc:
            reward = -0.2
            done = False
            error = str(exc)

        rewards.append(reward)
        steps_taken = step
        log_step(step=step, action=action, reward=reward, done=done, error=error)

        history.append(
            f"step={step} ticket={action['ticket_id']} "
            f"category={action['predicted_category']} "
            f"priority={action['predicted_priority']} "
            f"team={action['assigned_team']} reward={reward:.3f}"
        )

        if error is not None:
            break
        if done:
            break

    final_score = obs.get("final_score")
    if final_score is not None:
        score = clamp(float(final_score))
    elif rewards:
        score = clamp(sum(rewards) / max(float(len(rewards)), 1.0))
    else:
        score = 0.0

    success = score >= SUCCESS_SCORE_THRESHOLD
    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    # Allow running with heuristic fallback if API credentials are missing
    client: Optional[OpenAI] = None
    if API_BASE_URL and MODEL_NAME and API_KEY:
        client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    else:
        print("[DEBUG] Running with heuristic fallback (no API credentials)", flush=True)

    env = EnvHTTPClient(ENV_BASE_URL)
    try:
        for task_id in TASK_IDS:
            await run_task(env=env, client=client, task_id=task_id)
    finally:
        try:
            await env.close()
        except Exception as exc:
            print(f"[DEBUG] env.close() error: {exc}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
