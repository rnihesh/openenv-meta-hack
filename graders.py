"""Deterministic graders for Ticket Triage tasks."""

from dataclasses import dataclass
from typing import Dict, Mapping, Protocol

try:
    from .tasks import TASK_LIBRARY, TaskSpec, TicketSpec
except ImportError:  # pragma: no cover
    from tasks import TASK_LIBRARY, TaskSpec, TicketSpec


class ActionLike(Protocol):
    """Minimal action shape required for deterministic grading."""

    ticket_id: str
    predicted_category: str
    predicted_priority: str
    assigned_team: str
    resolution_summary: str


@dataclass(frozen=True)
class TicketGrade:
    """Per-ticket grade in [0.0, 1.0]."""

    ticket_id: str
    category_score: float
    priority_score: float
    team_score: float
    keyword_score: float

    @property
    def score(self) -> float:
        weighted = (
            0.4 * self.category_score
            + 0.25 * self.priority_score
            + 0.25 * self.team_score
            + 0.1 * self.keyword_score
        )
        return clamp(weighted, 0.0, 1.0)


@dataclass(frozen=True)
class EpisodeGrade:
    """Task-level grade summary."""

    task_id: str
    per_ticket: Dict[str, TicketGrade]
    completion_ratio: float
    running_score: float
    final_score: float


def clamp(value: float, low: float, high: float) -> float:
    """Clamp a numeric value into [low, high]."""

    return max(low, min(value, high))


def _keyword_score(ticket: TicketSpec, summary: str) -> float:
    lowered = summary.lower()
    matches = sum(1 for keyword in ticket.required_keywords if keyword.lower() in lowered)
    return clamp(matches / float(len(ticket.required_keywords)), 0.0, 1.0)


def evaluate_ticket(ticket: TicketSpec, action: ActionLike) -> TicketGrade:
    """Evaluate one action against one ticket deterministically."""

    category_score = 1.0 if action.predicted_category == ticket.expected_category else 0.0
    priority_score = 1.0 if action.predicted_priority == ticket.expected_priority else 0.0
    team_score = 1.0 if action.assigned_team == ticket.expected_team else 0.0
    keyword_score = _keyword_score(ticket, action.resolution_summary)

    return TicketGrade(
        ticket_id=ticket.ticket_id,
        category_score=category_score,
        priority_score=priority_score,
        team_score=team_score,
        keyword_score=keyword_score,
    )


def _running_score(grades: Mapping[str, TicketGrade]) -> float:
    if not grades:
        return 0.0
    mean_score = sum(grade.score for grade in grades.values()) / float(len(grades))
    return clamp(mean_score, 0.0, 1.0)


def grade_task(
    task_id: str,
    submitted_actions: Mapping[str, ActionLike],
    penalties: float = 0.0,
) -> EpisodeGrade:
    """
    Grade a task using deterministic criteria.

    Returns:
        EpisodeGrade with running_score and final_score in [0.0, 1.0].
    """

    if task_id not in TASK_LIBRARY:
        raise ValueError(f"Unknown task_id: {task_id}")

    task: TaskSpec = TASK_LIBRARY[task_id]
    grades: Dict[str, TicketGrade] = {}

    for ticket in task.tickets:
        action = submitted_actions.get(ticket.ticket_id)
        if action is None:
            continue
        grades[ticket.ticket_id] = evaluate_ticket(ticket, action)

    completion_ratio = clamp(len(grades) / float(len(task.tickets)), 0.0, 1.0)
    running_score = _running_score(grades)

    # Final score rewards both correctness and full completion.
    final_score = clamp((running_score * completion_ratio) - penalties, 0.0, 1.0)

    return EpisodeGrade(
        task_id=task_id,
        per_ticket=grades,
        completion_ratio=completion_ratio,
        running_score=running_score,
        final_score=final_score,
    )
