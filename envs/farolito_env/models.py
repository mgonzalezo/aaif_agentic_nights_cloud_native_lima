from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class FarolitoAction(Action):
    """What the agent sends: a full replacement for farolito/cli.py, or a unified diff."""

    cli_py: str | None = Field(default=None, description="Full replacement text for farolito/cli.py")
    diff: str | None = Field(default=None, description="Unified diff, applied with patch -p1 at the repo root")


class FarolitoObservation(Observation):
    """done and reward come from the base class. reward is 1.0 when the tests pass, else 0.0."""

    issue: str = ""
    files: list[str] = Field(default_factory=list)
    pytest_tail: str = ""
