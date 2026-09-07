"""OpenID Connect authorization-code flow backed by Microsoft Entra ID."""

import logging

import msal
from fastapi import APIRouter, HTTPException, Request, status
from starlette.responses import RedirectResponse

from app.auth.identity import CurrentUser, clear_identity, store_identity
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

FLOW_SESSION_KEY = "cchair_auth_flow"
RETURN_SESSION_KEY = "cchair_auth_return_to"
GRAPH_SCOPES = ["User.Read"]


def _client() -> msal.ConfidentialClientApplication:
    settings = get_settings()
    if not settings.auth_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Entra sign-in is enabled but not configured. Set CCHAIR_AUTH_TENANT_ID, "
            "CCHAIR_AUTH_CLIENT_ID and CCHAIR_AUTH_CLIENT_SECRET.",
        )
    return msal.ConfidentialClientApplication(
        client_id=settings.auth_client_id,
        client_credential=settings.auth_client_secret,
        authority=settings.auth_authority,
    )


def _redirect_uri(request: Request) -> str:
    return str(request.base_url).rstrip("/") + get_settings().auth_redirect_path


@router.get("/login")
def login(request: Request, return_to: str = "/") -> RedirectResponse:
    flow = _client().initiate_auth_code_flow(scopes=GRAPH_SCOPES, redirect_uri=_redirect_uri(request))
    request.session[FLOW_SESSION_KEY] = flow
    request.session[RETURN_SESSION_KEY] = return_to
    return RedirectResponse(flow["auth_uri"], status_code=status.HTTP_302_FOUND)


@router.get("/callback")
def callback(request: Request) -> RedirectResponse:
    flow = request.session.pop(FLOW_SESSION_KEY, None)
    if not flow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sign-in session expired. Start again from /auth/login.",
        )

    result = _client().acquire_token_by_auth_code_flow(flow, dict(request.query_params))
    if "error" in result:
        logger.warning("Entra sign-in failed: %s", result.get("error_description", result["error"]))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Sign-in failed: {result.get('error_description', result['error'])}",
        )

    claims = result.get("id_token_claims", {})
    user = CurrentUser(
        object_id=claims.get("oid", ""),
        upn=claims.get("preferred_username") or claims.get("upn", ""),
        display_name=claims.get("name", ""),
    )
    if not user.upn:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign-in succeeded but the token contained no user principal name.",
        )

    store_identity(request, user)
    return RedirectResponse(request.session.pop(RETURN_SESSION_KEY, "/"), status_code=status.HTTP_302_FOUND)


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    clear_identity(request)
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)
