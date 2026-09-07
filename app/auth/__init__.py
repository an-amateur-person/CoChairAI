"""Microsoft Entra sign-in and request identity for CoChairAI."""

from app.auth.identity import CurrentUser, clear_identity, read_identity, store_identity
from app.auth.dependencies import optional_user, require_approver, require_user

__all__ = [
    "CurrentUser",
    "clear_identity",
    "optional_user",
    "read_identity",
    "require_approver",
    "require_user",
    "store_identity",
]
