"""Ticket Triage environment client."""

from typing import Dict, List, Optional

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

try:
    from .models import (
        TicketSnapshot,
        TicketTriageAction,
        TicketTriageObservation,
        TicketTriageReward,
    )
except ImportError:  # pragma: no cover
    from models import TicketSnapshot, TicketTriageAction, TicketTriageObservation, TicketTriageReward


class TicketTriageEnv(EnvClient[TicketTriageAction, TicketTriageObservation, State]):
    """Typed OpenEnv client for the Ticket Triage benchmark."""

    def _step_payload(self, action: TicketTriageAction) -> Dict:
        return {
            "ticket_id": action.ticket_id,
            "predicted_category": action.predicted_category,
            "predicted_priority": action.predicted_priority,
            "assigned_team": action.assigned_team,
            "resolution_summary": action.resolution_summary,
            "finalize": action.finalize,
        }

    def _parse_result(self, payload: Dict) -> StepResult[TicketTriageObservation]:
        obs_data = payload.get("observation", {})
        observation = self._parse_observation(obs_data, payload)
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_observation(self, obs_data: Dict, payload: Dict) -> TicketTriageObservation:
        tickets: List[TicketSnapshot] = []
        for item in obs_data.get("tickets", []):
            if isinstance(item, dict):
                tickets.append(TicketSnapshot(**item))

        reward_details_data: Optional[Dict] = obs_data.get("reward_details")
        reward_details = (
            TicketTriageReward(**reward_details_data)
            if isinstance(reward_details_data, dict)
            else None
        )

        return TicketTriageObservation(
            task_id=obs_data.get("task_id", ""),
            difficulty=obs_data.get("difficulty", ""),
            objective=obs_data.get("objective", ""),
            tickets=tickets,
            pending_ticket_ids=list(obs_data.get("pending_ticket_ids", [])),
            triaged_ticket_ids=list(obs_data.get("triaged_ticket_ids", [])),
            last_feedback=obs_data.get("last_feedback", ""),
            running_score=float(obs_data.get("running_score", 0.0)),
            final_score=obs_data.get("final_score"),
            reward_details=reward_details,
            done=payload.get("done", False),
            reward=payload.get("reward"),
            metadata=obs_data.get("metadata", {}),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
