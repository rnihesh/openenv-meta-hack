"""Typed models for the Ticket Triage environment."""

from typing import Dict, List, Literal, Optional

from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field

Category = Literal["billing", "technical", "account", "abuse", "shipping"]
Priority = Literal["low", "medium", "high", "urgent"]
Team = Literal[
    "billing_ops",
    "tech_support",
    "account_services",
    "trust_safety",
    "fulfillment",
]


class TicketTriageReward(BaseModel):
    """Typed reward object with score decomposition."""

    value: float = Field(..., description="Final step reward in range [-1.0, 1.0]")
    components: Dict[str, float] = Field(
        default_factory=dict,
        description="Named reward components used to compute `value`.",
    )
    reason: str = Field(default="", description="Human-readable explanation for this reward.")


class TicketSnapshot(BaseModel):
    """Read-only ticket view presented to the agent."""

    ticket_id: str = Field(..., description="Stable ticket identifier.")
    customer_message: str = Field(..., description="Customer issue text.")
    sla_hours: int = Field(..., description="Hours remaining before SLA violation.")
    status: Literal["pending", "triaged"] = Field(
        ..., description="Current ticket status in this episode."
    )


class TicketTriageAction(Action):
    """Action submitted by the agent at each step."""

    ticket_id: str = Field(..., description="Ticket to triage in this step.")
    predicted_category: Category = Field(..., description="Predicted ticket category.")
    predicted_priority: Priority = Field(..., description="Predicted urgency level.")
    assigned_team: Team = Field(..., description="Operational team that should own the ticket.")
    resolution_summary: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Short response/escalation summary for the customer and internal team.",
    )
    finalize: bool = Field(
        default=False,
        description="If true, request episode completion once all tickets are triaged.",
    )


class TicketTriageObservation(Observation):
    """Observation returned after `reset()` and each `step()` call."""

    task_id: str = Field(..., description="Task identifier: easy, medium, or hard.")
    difficulty: str = Field(..., description="Difficulty label for the active task.")
    objective: str = Field(..., description="Task objective/instructions shown to the agent.")
    tickets: List[TicketSnapshot] = Field(
        default_factory=list,
        description="Current ticket queue snapshot.",
    )
    pending_ticket_ids: List[str] = Field(
        default_factory=list,
        description="Tickets that still require triage actions.",
    )
    triaged_ticket_ids: List[str] = Field(
        default_factory=list,
        description="Tickets already triaged by the agent.",
    )
    last_feedback: str = Field(
        default="",
        description="Feedback generated from the previous action.",
    )
    running_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Current task score estimate from completed tickets.",
    )
    final_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Final deterministic task score when episode is done.",
    )
    reward_details: Optional[TicketTriageReward] = Field(
        default=None,
        description="Structured reward object for this step.",
    )
