"""Task registry for the Ticket Triage environment."""

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class TicketSpec:
    """Ground-truth ticket specification for grading."""

    ticket_id: str
    customer_message: str
    expected_category: str
    expected_priority: str
    expected_team: str
    required_keywords: Tuple[str, ...]
    sla_hours: int


@dataclass(frozen=True)
class TaskSpec:
    """One benchmark task with fixed tickets and constraints."""

    task_id: str
    name: str
    difficulty: str
    objective: str
    max_steps: int
    tickets: Tuple[TicketSpec, ...]


TASK_LIBRARY: Dict[str, TaskSpec] = {
    "easy": TaskSpec(
        task_id="easy",
        name="Straightforward Inbox",
        difficulty="easy",
        objective=(
            "Triage two clear support tickets by selecting the right category, priority, "
            "team, and a concise resolution summary."
        ),
        max_steps=4,
        tickets=(
            TicketSpec(
                ticket_id="E-1001",
                customer_message=(
                    "I was charged twice for my annual subscription this morning. "
                    "Please refund the duplicate payment."
                ),
                expected_category="billing",
                expected_priority="high",
                expected_team="billing_ops",
                required_keywords=("refund", "duplicate"),
                sla_hours=8,
            ),
            TicketSpec(
                ticket_id="E-1002",
                customer_message=(
                    "Password reset link never arrives and I need account access "
                    "before tomorrow's presentation."
                ),
                expected_category="account",
                expected_priority="medium",
                expected_team="account_services",
                required_keywords=("reset", "verification"),
                sla_hours=18,
            ),
        ),
    ),
    "medium": TaskSpec(
        task_id="medium",
        name="Mixed Operations Queue",
        difficulty="medium",
        objective=(
            "Triage three tickets spanning technical, shipping, and security concerns. "
            "Use urgency and routing decisions that reflect operational risk."
        ),
        max_steps=6,
        tickets=(
            TicketSpec(
                ticket_id="M-2101",
                customer_message=(
                    "After the iOS 17 update, the app crashes whenever I start screen "
                    "recording. This blocks all my demos."
                ),
                expected_category="technical",
                expected_priority="high",
                expected_team="tech_support",
                required_keywords=("logs", "reinstall"),
                sla_hours=10,
            ),
            TicketSpec(
                ticket_id="M-2102",
                customer_message=(
                    "My order has not shipped yet and the address needs to be corrected "
                    "today before dispatch."
                ),
                expected_category="shipping",
                expected_priority="medium",
                expected_team="fulfillment",
                required_keywords=("address", "shipment"),
                sla_hours=16,
            ),
            TicketSpec(
                ticket_id="M-2103",
                customer_message=(
                    "I received a login alert from a country I have never visited and "
                    "my 2FA is suddenly disabled."
                ),
                expected_category="abuse",
                expected_priority="urgent",
                expected_team="trust_safety",
                required_keywords=("secure", "2fa"),
                sla_hours=2,
            ),
        ),
    ),
    "hard": TaskSpec(
        task_id="hard",
        name="High-Stakes Escalation",
        difficulty="hard",
        objective=(
            "Triage four complex tickets with legal/compliance pressure, abuse risk, "
            "and technical ambiguity. Correct escalation quality matters."
        ),
        max_steps=8,
        tickets=(
            TicketSpec(
                ticket_id="H-3301",
                customer_message=(
                    "Our enterprise invoice total is wrong and legal needs a corrected "
                    "statement before tomorrow's contract deadline."
                ),
                expected_category="billing",
                expected_priority="urgent",
                expected_team="billing_ops",
                required_keywords=("invoice", "deadline"),
                sla_hours=4,
            ),
            TicketSpec(
                ticket_id="H-3302",
                customer_message=(
                    "A creator is being harassed in direct messages. We have screenshots "
                    "and need immediate intervention."
                ),
                expected_category="abuse",
                expected_priority="urgent",
                expected_team="trust_safety",
                required_keywords=("escalate", "evidence"),
                sla_hours=1,
            ),
            TicketSpec(
                ticket_id="H-3303",
                customer_message=(
                    "CSV exports become corrupted only on weekends in UTC, and auditors "
                    "require clean exports for a compliance review."
                ),
                expected_category="technical",
                expected_priority="high",
                expected_team="tech_support",
                required_keywords=("reproduce", "audit"),
                sla_hours=6,
            ),
            TicketSpec(
                ticket_id="H-3304",
                customer_message=(
                    "Someone took over my account and created unknown API keys. I need "
                    "those keys revoked and an investigation started now."
                ),
                expected_category="account",
                expected_priority="urgent",
                expected_team="trust_safety",
                required_keywords=("revoke", "investigate"),
                sla_hours=1,
            ),
        ),
    ),
}


def list_task_ids() -> Tuple[str, ...]:
    """Return task identifiers in benchmark order."""

    return ("easy", "medium", "hard")
