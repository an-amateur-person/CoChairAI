"""FastAPI dependencies that enforce authentication and approval rights."""

from fastapi import Depends, HTTPException, Request, status

from app.auth.identity import CurrentUser, read_identity


def optional_user(request: Request) -> CurrentUser | None:
    return read_identity(request)


def require_user(request: Request) -> CurrentUser:
    user = read_identity(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in with your organizational account to use this API.",
        )
    return user


def require_approver(user: CurrentUser = Depends(require_user)) -> CurrentUser:
    if not user.is_approver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{user.upn} is not authorized to approve.",
        )
    return user
