"""Signed-in user representation and session persistence."""

from dataclasses import dataclass
from typing import Any

from starlette.requests import Request

from app.config import get_settings

SESSION_KEY = "cchair_identity"


@dataclass(frozen=True)
class CurrentUser:
    object_id: str
    upn: str
    display_name: str

    @property
    def is_approver(self) -> bool:
        """An empty approver list means any signed-in user may approve."""
        approvers = get_settings().approvers
        return not approvers or self.upn.lower() in approvers

    def as_claims(self) -> dict[str, str]:
        return {"object_id": self.object_id, "upn": self.upn, "display_name": self.display_name}


def _development_user() -> CurrentUser:
    settings = get_settings()
    return CurrentUser(
        object_id="00000000-0000-0000-0000-000000000000",
        upn=settings.dev_user_upn,
        display_name=settings.dev_user_name,
    )


def _session(request: Request | None) -> dict[str, Any] | None:
    if request is None:
        return None
    try:
        return request.session
    except (AssertionError, AttributeError):
        return None


def _request_from_context() -> Request | None:
    """Resolve the request from the NiceGUI page context when one is active."""
    try:
        from nicegui import context

        return context.client.request
    except Exception:
        return None


def store_identity(request: Request, user: CurrentUser) -> None:
    session = _session(request)
    if session is not None:
        session[SESSION_KEY] = user.as_claims()


def clear_identity(request: Request) -> None:
    session = _session(request)
    if session is not None:
        session.pop(SESSION_KEY, None)


def read_identity(request: Request | None = None) -> CurrentUser | None:
    """Return the signed-in user, or the development identity when auth is disabled."""
    if not get_settings().auth_enabled:
        return _development_user()

    session = _session(request if request is not None else _request_from_context())
    claims = session.get(SESSION_KEY) if session else None
    if not claims:
        return None
    return CurrentUser(
        object_id=claims.get("object_id", ""),
        upn=claims.get("upn", ""),
        display_name=claims.get("display_name", ""),
    )
