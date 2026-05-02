"""
governance/access_control/rbac.py
Role-based access control for model and feature access.
Integrates with the gateway layer to enforce permissions at the tool-call level.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Callable


class Role(str, Enum):
    VIEWER = "viewer"           # Read-only: query models, view dashboards
    DEVELOPER = "developer"     # Can deploy prompts, run evals
    ML_ENGINEER = "ml_engineer" # Can fine-tune models, manage registry
    ADMIN = "admin"             # Full access including audit logs, cost data


# Permission → minimum required role
PERMISSIONS: dict[str, Role] = {
    "chat:completion":        Role.VIEWER,
    "rag:query":              Role.VIEWER,
    "prompt:read":            Role.VIEWER,
    "prompt:write":           Role.DEVELOPER,
    "eval:run":               Role.DEVELOPER,
    "model:deploy":           Role.ML_ENGINEER,
    "model:fine_tune":        Role.ML_ENGINEER,
    "model:registry:write":   Role.ML_ENGINEER,
    "audit:read":             Role.ADMIN,
    "cost:read":              Role.DEVELOPER,
    "cost:admin":             Role.ADMIN,
}

_ROLE_HIERARCHY: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.DEVELOPER: 1,
    Role.ML_ENGINEER: 2,
    Role.ADMIN: 3,
}


@dataclass
class User:
    id: str
    role: Role
    team_id: str = "default"
    model_allowlist: list[str] = field(default_factory=list)  # Empty = all models allowed


class AccessDenied(Exception):
    pass


class RBACEnforcer:
    def check(self, user: User, permission: str) -> bool:
        required_role = PERMISSIONS.get(permission)
        if required_role is None:
            raise ValueError(f"Unknown permission: {permission}")
        return _ROLE_HIERARCHY[user.role] >= _ROLE_HIERARCHY[required_role]

    def enforce(self, user: User, permission: str) -> None:
        if not self.check(user, permission):
            raise AccessDenied(
                f"User '{user.id}' with role '{user.role}' "
                f"lacks permission '{permission}'"
            )

    def check_model_access(self, user: User, model: str) -> bool:
        if not user.model_allowlist:
            return True   # Empty allowlist = all models permitted
        return model in user.model_allowlist

    def enforce_model_access(self, user: User, model: str) -> None:
        if not self.check_model_access(user, model):
            raise AccessDenied(
                f"User '{user.id}' is not permitted to access model '{model}'. "
                f"Allowed: {user.model_allowlist}"
            )


# Singleton enforcer
_enforcer = RBACEnforcer()


def require_permission(permission: str):
    """Decorator for functions that accept a `user: User` keyword argument."""
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, user: User, **kwargs):
            _enforcer.enforce(user, permission)
            return fn(*args, user=user, **kwargs)
        return wrapper
    return decorator
