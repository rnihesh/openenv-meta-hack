---
title: Ticket Triage OpenEnv
emoji: 📥
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
tags:
  - openenv
---

# ticket_triage_env

A real-world OpenEnv benchmark where an agent triages customer support tickets.

This environment simulates a support operations queue with deterministic grading over three tasks (`easy`, `medium`, `hard`).

## Why this environment

Support triage is a practical agent workflow used in SaaS, e-commerce, and trust/safety operations. The benchmark measures whether an agent can:

- classify issue type correctly,
- assign the right urgency,
- route to the right team,
- produce a meaningful resolution summary.

## OpenEnv API

The server exposes standard OpenEnv APIs via `step()`, `reset()`, and `state()`.

### Action space

`TicketTriageAction` fields:

- `ticket_id` (`str`): ticket selected for triage.
- `predicted_category` (`billing|technical|account|abuse|shipping`)
- `predicted_priority` (`low|medium|high|urgent`)
- `assigned_team` (`billing_ops|tech_support|account_services|trust_safety|fulfillment`)
- `resolution_summary` (`str`): short human-readable triage summary.
- `finalize` (`bool`): request episode completion once all tickets are triaged.

### Observation space

`TicketTriageObservation` fields:

- `task_id`, `difficulty`, `objective`
- `tickets`: list of ticket snapshots (`ticket_id`, `customer_message`, `sla_hours`, `status`)
- `pending_ticket_ids`, `triaged_ticket_ids`
- `last_feedback`
- `running_score` (0.0-1.0)
- `final_score` (0.0-1.0 when done)
- `reward_details`: typed reward object (`value`, `components`, `reason`)

### Reward model

Per-step reward is shaped and clamped to `[-1.0, 1.0]`.

Positive components:

- `classification_score` (weighted correctness for category/priority/team/keywords)
- `progress_bonus` (+0.15 for first-time triage)
- `completion_bonus` (+0.20 once all tickets are triaged)

Negative components:

- invalid ticket / duplicate ticket penalties
- premature finalize penalty
- max-step truncation penalty
- destructive summary penalty (for unsafe/no-op behavior)

## Tasks and graders

Deterministic graders are implemented in `graders.py` and return scores in `[0.0, 1.0]`.

- `easy`: 2 straightforward tickets (`max_steps=4`)
- `medium`: 3 mixed operational tickets (`max_steps=6`)
- `hard`: 4 high-stakes escalation tickets (`max_steps=8`)

Task grading combines:

1. per-ticket weighted correctness,
2. completion ratio,
3. explicit episode penalties.

## Setup

### 1) Install dependencies

```bash
pip install -e .
```

### 2) Run server locally

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### 3) Build and run Docker

```bash
docker build -t ticket-triage-env:latest -f server/Dockerfile .
docker run --rm -p 8000:8000 ticket-triage-env:latest
```

## Baseline inference

The benchmark script is required at root and is provided as `inference.py`.

Environment variables required by the challenge:

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

Optional:

- `IMAGE_NAME` (default: `ticket-triage-env:latest`)
- `MAX_STEPS`
- `SUCCESS_SCORE_THRESHOLD`

Run:

```bash
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="<token>"
python inference.py
```

The script emits structured logs in `[START]`, `[STEP]`, and `[END]` format for each task.

## Expected baseline (heuristic fallback)

Deterministic fallback policy (used when model call fails) typically produces:

- `easy`: `~0.82`
- `medium`: `~0.66`
- `hard`: `~0.58`
- average: `~0.69`

Your exact score depends on model behavior and endpoint configuration.

## Validation checklist

Before submission:

```bash
openenv validate --verbose
```

and run the organizer script (from prompt):

```bash
./validate-submission.sh <your_hf_space_url> .
```

## Project layout

```text
.
├── __init__.py
├── client.py
├── graders.py
├── inference.py
├── models.py
├── openenv.yaml
├── pyproject.toml
├── tasks.py
└── server/
    ├── app.py
    ├── Dockerfile
    ├── requirements.txt
    └── ticket_triage_environment.py
```
