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
except (ModuleNotFoundError, ImportError):  # pragma: no cover
    from models import TicketTriageAction, TicketTriageObservation
    from server.ticket_triage_environment import TicketTriageEnvironment

# Singleton environment instance — the HTTP server calls the factory on every
# step/reset, so we return the same instance to preserve episode state.
_env_instance = TicketTriageEnvironment()


def _env_factory() -> TicketTriageEnvironment:
    return _env_instance


app = create_app(
    _env_factory,
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
    main()
