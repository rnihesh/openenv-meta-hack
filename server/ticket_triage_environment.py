"""Ticket triage environment implementation."""

import random
from typing import Any, Dict, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..graders import EpisodeGrade, evaluate_ticket, grade_task
    from ..models import TicketSnapshot, TicketTriageAction, TicketTriageObservation, TicketTriageReward
    from ..tasks import TASK_LIBRARY, TaskSpec, list_task_ids
except ImportError:  # pragma: no cover
    from graders import EpisodeGrade, evaluate_ticket, grade_task
    from models import TicketSnapshot, TicketTriageAction, TicketTriageObservation, TicketTriageReward
    from tasks import TASK_LIBRARY, TaskSpec, list_task_ids


def clamp(value: float, low: float, high: float) -> float:
    """Clamp to a bounded interval."""

    return max(low, min(value, high))


class TicketTriageEnvironment(Environment):
    """Real-world environment for customer support ticket triage."""

    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    DESTRUCTIVE_HINTS = ("ignore", "drop", "delete", "erase", "close without action")

    def __init__(self):
        self._rng = random.Random(0)
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._task: TaskSpec = TASK_LIBRARY["easy"]
        self._submitted_actions: Dict[str, TicketTriageAction] = {}
        self._episode_penalties: float = 0.0
        self._done: bool = False
        self._last_feedback: str = "Environment initialized. Call reset() to begin."

    def reset(
        self,
        seed: Optional[int] = None,
        task_id: Optional[str] = None,
        **kwargs: Any,
    ) -> TicketTriageObservation:
        """Reset state and choose one benchmark task."""

        requested_task_id = task_id or kwargs.get("task_id")
        if seed is not None:
            self._rng.seed(seed)

        if requested_task_id in TASK_LIBRARY:
            selected_task_id = requested_task_id
            source = "requested"
        elif requested_task_id is None:
            selected_task_id = "easy"
            source = "default"
        else:
            selected_task_id = "easy"
            source = "fallback"

        self._task = TASK_LIBRARY[selected_task_id]
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._submitted_actions = {}
        self._episode_penalties = 0.0
        self._done = False

        if source == "requested":
            self._last_feedback = f"Loaded task '{selected_task_id}'."
        elif source == "fallback":
            valid = ", ".join(list_task_ids())
            self._last_feedback = (
                f"Unknown task_id '{requested_task_id}'. Loaded 'easy'. Valid task_ids: {valid}."
            )
        else:
            self._last_feedback = "Loaded default task 'easy'."

        reward_details = TicketTriageReward(
            value=0.0,
            components={"reset": 0.0},
            reason=self._last_feedback,
        )
        return self._build_observation(reward=0.0, reward_details=reward_details)

    def step(self, action: TicketTriageAction) -> TicketTriageObservation:  # type: ignore[override]
        """Apply one triage decision and return shaped reward."""

        self._state.step_count += 1

        if self._done:
            self._last_feedback = "Episode already completed. Call reset() to start a new task."
            reward_details = TicketTriageReward(
                value=-0.05,
                components={"after_done_penalty": -0.05},
                reason=self._last_feedback,
            )
            return self._build_observation(reward=-0.05, reward_details=reward_details)

        components: Dict[str, float] = {}
        ticket_lookup = {ticket.ticket_id: ticket for ticket in self._task.tickets}
        ticket = ticket_lookup.get(action.ticket_id)

        if ticket is None:
            components["invalid_ticket_penalty"] = -0.25
            self._episode_penalties += 0.05
            self._last_feedback = (
                f"Ticket '{action.ticket_id}' is not part of task '{self._task.task_id}'."
            )
        elif action.ticket_id in self._submitted_actions:
            components["duplicate_ticket_penalty"] = -0.15
            self._episode_penalties += 0.03
            self._last_feedback = f"Ticket '{action.ticket_id}' was already triaged."
        else:
            grade = evaluate_ticket(ticket, action)
            self._submitted_actions[action.ticket_id] = action

            components["classification_score"] = grade.score
            components["progress_bonus"] = 0.15

            destructive_penalty = self._destructive_penalty(action.resolution_summary)
            if destructive_penalty > 0:
                components["destructive_summary_penalty"] = -destructive_penalty
                self._episode_penalties += 0.04

            self._last_feedback = (
                f"Triaged '{action.ticket_id}': category={grade.category_score:.0f}, "
                f"priority={grade.priority_score:.0f}, team={grade.team_score:.0f}, "
                f"keyword={grade.keyword_score:.2f}."
            )

        if action.finalize and len(self._submitted_actions) < len(self._task.tickets):
            components["premature_finalize_penalty"] = -0.1
            self._episode_penalties += 0.02

        all_triaged = len(self._submitted_actions) == len(self._task.tickets)
        if all_triaged:
            self._done = True
            components["completion_bonus"] = 0.2

        if self._state.step_count >= self._task.max_steps:
            self._done = True
            if not all_triaged:
                components["max_step_penalty"] = -0.1
                self._episode_penalties += 0.05
                self._last_feedback += " Reached max steps before triaging all tickets."

        reward_value = clamp(sum(components.values()), -1.0, 1.0)
        reward_details = TicketTriageReward(
            value=reward_value,
            components=components,
            reason=self._last_feedback,
        )

        return self._build_observation(reward=reward_value, reward_details=reward_details)

    @property
    def state(self) -> State:
        """Return current OpenEnv state."""

        return self._state

    def _destructive_penalty(self, summary: str) -> float:
        lowered = summary.lower()
        for token in self.DESTRUCTIVE_HINTS:
            if token in lowered:
                return 0.15
        return 0.0

    def _build_observation(
        self,
        reward: float,
        reward_details: TicketTriageReward,
    ) -> TicketTriageObservation:
        grade: EpisodeGrade = grade_task(
            self._task.task_id,
            self._submitted_actions,
            penalties=self._episode_penalties,
        )

        triaged_ids = list(self._submitted_actions.keys())
        pending_ids = [
            ticket.ticket_id for ticket in self._task.tickets if ticket.ticket_id not in self._submitted_actions
        ]

        snapshots = [
            TicketSnapshot(
                ticket_id=ticket.ticket_id,
                customer_message=ticket.customer_message,
                sla_hours=ticket.sla_hours,
                status="triaged" if ticket.ticket_id in self._submitted_actions else "pending",
            )
            for ticket in self._task.tickets
        ]

        per_ticket_scores = {
            ticket_id: ticket_grade.score
            for ticket_id, ticket_grade in grade.per_ticket.items()
        }

        metadata = {
            "task_name": self._task.name,
            "steps_remaining": max(0, self._task.max_steps - self._state.step_count),
            "completion_ratio": grade.completion_ratio,
            "episode_penalties": self._episode_penalties,
            "per_ticket_scores": per_ticket_scores,
        }

        return TicketTriageObservation(
            task_id=self._task.task_id,
            difficulty=self._task.difficulty,
            objective=self._task.objective,
            tickets=snapshots,
            pending_ticket_ids=pending_ids,
            triaged_ticket_ids=triaged_ids,
            last_feedback=self._last_feedback,
            running_score=grade.running_score,
            final_score=grade.final_score if self._done else None,
            reward_details=reward_details,
            done=self._done,
            reward=reward,
            metadata=metadata,
        )
