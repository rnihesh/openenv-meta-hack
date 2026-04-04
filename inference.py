"""Baseline inference script for ticket_triage_env.

Required environment variables:
- API_BASE_URL
- MODEL_NAME
- HF_TOKEN

Optional:
- IMAGE_NAME (default: ticket-triage-env:latest)
- MAX_STEPS
- SUCCESS_SCORE_THRESHOLD
"""

import asyncio
import json
import os
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI

from client import TicketTriageEnv
from models import TicketSnapshot, TicketTriageAction, TicketTriageObservation
from tasks import list_task_ids

BENCHMARK = "ticket_triage_env"
API_BASE_URL = os.getenv("API_BASE_URL", "").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "").strip()
API_KEY = (os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY") or "").strip()
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


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def log_start(task: str, env: str, model: str) -> None:
    payload = {"task": task, "env": env, "model": model}
    print(f"[START] {json.dumps(payload, ensure_ascii=True)}", flush=True)


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
        "rewards": [round(float(item), 6) for item in rewards],
    }
    print(f"[END] {json.dumps(payload, ensure_ascii=True)}", flush=True)


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
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in allowed:
            return lowered
    return default


def _find_ticket(observation: TicketTriageObservation, ticket_id: str) -> Optional[TicketSnapshot]:
    for ticket in observation.tickets:
        if ticket.ticket_id == ticket_id:
            return ticket
    return None


def heuristic_action(observation: TicketTriageObservation) -> TicketTriageAction:
    if not observation.pending_ticket_ids:
        fallback_ticket = observation.triaged_ticket_ids[-1] if observation.triaged_ticket_ids else ""
        return TicketTriageAction(
            ticket_id=fallback_ticket,
            predicted_category="technical",
            predicted_priority="low",
            assigned_team="tech_support",
            resolution_summary="No pending ticket. Ask for reset.",
            finalize=True,
        )

    ticket_id = observation.pending_ticket_ids[0]
    ticket = _find_ticket(observation, ticket_id)
    message = ticket.customer_message.lower() if ticket else ""

    if any(token in message for token in ["refund", "charged", "invoice", "payment"]):
        category = "billing"
    elif any(token in message for token in ["harass", "abuse", "threat", "suspicious", "take over"]):
        category = "abuse"
    elif any(token in message for token in ["address", "shipment", "order", "dispatch"]):
        category = "shipping"
    elif any(token in message for token in ["password", "login", "2fa", "account", "api key"]):
        category = "account"
    else:
        category = "technical"

    if any(token in message for token in ["urgent", "immediate", "now", "deadline", "harass", "take over"]):
        priority = "urgent"
    elif any(token in message for token in ["blocked", "crash", "charged twice", "legal"]):
        priority = "high"
    elif any(token in message for token in ["today", "tomorrow", "before"]):
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
    if category == "account" and any(token in message for token in ["suspicious", "take over", "api key"]):
        team = "trust_safety"

    summary_tokens = ["review", "customer", "follow-up"]
    if category == "billing":
        summary_tokens = ["invoice", "refund", "deadline"]
    elif category == "abuse":
        summary_tokens = ["escalate", "evidence", "secure"]
    elif category == "technical":
        summary_tokens = ["reproduce", "logs", "audit"]
    elif category == "shipping":
        summary_tokens = ["address", "shipment", "confirm"]
    elif category == "account":
        summary_tokens = ["reset", "verification", "investigate"]

    finalize = len(observation.pending_ticket_ids) == 1
    return TicketTriageAction(
        ticket_id=ticket_id,
        predicted_category=category,
        predicted_priority=priority,
        assigned_team=team,
        resolution_summary=" ".join(summary_tokens),
        finalize=finalize,
    )


def get_model_action(
    client: Optional[OpenAI],
    observation: TicketTriageObservation,
    history: List[str],
) -> TicketTriageAction:
    fallback = heuristic_action(observation)

    if client is None:
        return fallback

    prompt = {
        "task_id": observation.task_id,
        "objective": observation.objective,
        "pending_ticket_ids": observation.pending_ticket_ids,
        "tickets": [ticket.model_dump() for ticket in observation.tickets],
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
                        "You are a support operations assistant. Return exactly one JSON object "
                        "with the requested fields and no markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=True),
                },
            ],
        )
        message = response.choices[0].message.content or ""
        payload = _extract_json(message)
        if payload is None:
            return fallback

        return TicketTriageAction(
            ticket_id=str(payload.get("ticket_id", fallback.ticket_id)),
            predicted_category=_normalize(
                payload.get("predicted_category"),
                VALID_CATEGORIES,
                fallback.predicted_category,
            ),
            predicted_priority=_normalize(
                payload.get("predicted_priority"),
                VALID_PRIORITIES,
                fallback.predicted_priority,
            ),
            assigned_team=_normalize(
                payload.get("assigned_team"),
                VALID_TEAMS,
                fallback.assigned_team,
            ),
            resolution_summary=str(payload.get("resolution_summary", fallback.resolution_summary))[:500],
            finalize=bool(payload.get("finalize", fallback.finalize)),
        )
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return fallback


async def run_task(env: TicketTriageEnv, client: Optional[OpenAI], task_id: str) -> float:
    rewards: List[float] = []
    history: List[str] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    result = await env.reset(task_id=task_id)

    for step in range(1, MAX_STEPS + 1):
        if result.done:
            break

        action = get_model_action(client, result.observation, history)
        action_payload = action.model_dump()
        error: Optional[str] = None

        try:
            result = await env.step(action)
            reward = float(result.reward or 0.0)
            done = bool(result.done)
        except Exception as exc:
            reward = -0.2
            done = False
            error = str(exc)

        rewards.append(reward)
        steps_taken = step
        log_step(step=step, action=action_payload, reward=reward, done=done, error=error)

        history.append(
            f"step={step} ticket={action.ticket_id} category={action.predicted_category} "
            f"priority={action.predicted_priority} team={action.assigned_team} reward={reward:.3f}"
        )

        if error is not None:
            break
        if done:
            break

    final_obs = result.observation
    if final_obs.final_score is not None:
        score = clamp(float(final_obs.final_score), 0.0, 1.0)
    elif rewards:
        score = clamp(sum(rewards) / max(float(len(rewards)), 1.0), 0.0, 1.0)
    else:
        score = 0.0

    success = score >= SUCCESS_SCORE_THRESHOLD
    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score


async def main() -> None:
    required = [name for name in ("API_BASE_URL", "MODEL_NAME", "HF_TOKEN") if not os.getenv(name)]
    if required:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(required)
        )

    client: Optional[OpenAI]
    if API_KEY:
        client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    else:
        client = None

    env = await TicketTriageEnv.from_docker_image(IMAGE_NAME)
    try:
        for task_id in list_task_ids():
            await run_task(env=env, client=client, task_id=task_id)
    finally:
        try:
            await env.close()
        except Exception as exc:
            print(f"[DEBUG] env.close() error (container cleanup): {exc}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
