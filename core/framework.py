"""
Framework-wide maturity levels and stub policy helpers.

The project is a reusable LLMOps framework, so some integrations are
intentionally left as extension points. These helpers make that distinction
explicit: reference mode may use deterministic stubs, while production modes
must fail when a claimed gate has not been implemented.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class FrameworkMode(str, Enum):
    REFERENCE = "reference"
    STARTER_PRODUCTION = "starter-production"
    REGULATED_PRODUCTION = "regulated-production"
    MULTI_CLOUD_ENTERPRISE = "multi-cloud-enterprise"

    @property
    def allows_stubs(self) -> bool:
        return self is FrameworkMode.REFERENCE

    @property
    def is_production_path(self) -> bool:
        return self is not FrameworkMode.REFERENCE


@dataclass(frozen=True)
class StubDecision:
    allowed: bool
    reason: str


def get_framework_mode() -> FrameworkMode:
    """
    Resolve the current framework maturity mode.

    APP_COMPLEXITY is the preferred name. LLMOPS_FRAMEWORK_MODE is accepted as
    a descriptive alias for CI jobs and local scripts.
    """
    raw = (
        os.getenv("APP_COMPLEXITY")
        or os.getenv("LLMOPS_FRAMEWORK_MODE")
        or FrameworkMode.REFERENCE.value
    )
    try:
        return FrameworkMode(raw)
    except ValueError as exc:
        valid = ", ".join(mode.value for mode in FrameworkMode)
        raise ValueError(f"Unknown framework mode '{raw}'. Expected one of: {valid}") from exc


def decide_stub(feature: str, mode: FrameworkMode | None = None) -> StubDecision:
    current_mode = mode or get_framework_mode()
    if current_mode.allows_stubs:
        return StubDecision(
            allowed=True,
            reason=(
                f"{feature} is running in reference mode. This is an explicit "
                "framework stub for local development and documentation."
            ),
        )
    return StubDecision(
        allowed=False,
        reason=(
            f"{feature} is not implemented for {current_mode.value}. Production "
            "modes require a real implementation or a configured external gate."
        ),
    )


def require_env_vars(names: list[str], *, component: str) -> None:
    """Fail fast when a production-path component is missing required config."""
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"{component} is missing required environment variables: {joined}")
