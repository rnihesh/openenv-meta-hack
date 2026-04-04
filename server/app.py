"""FastAPI app for the Ticket Triage environment."""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "openenv-core is required. Install dependencies with `pip install -e .`."
    ) from exc

try:
    from ..models import TicketTriageAction, TicketTriageObservation
    from .ticket_triage_environment import TicketTriageEnvironment
except ModuleNotFoundError:  # pragma: no cover
    from models import TicketTriageAction, TicketTriageObservation
    from server.ticket_triage_environment import TicketTriageEnvironment


app = create_app(
    TicketTriageEnvironment,
    TicketTriageAction,
    TicketTriageObservation,
    env_name="ticket_triage_env",
    max_concurrent_envs=4,
)


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run the environment server."""

    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    main(port=args.port)
