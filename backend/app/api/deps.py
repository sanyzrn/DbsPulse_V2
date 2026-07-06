from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import CurrentUser

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="توکن نامعتبر یا منقضی‌شده است",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise unauthorized

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized
    if payload.get("tv") != user.token_version:
        raise unauthorized

    return CurrentUser(
        id=user.id,
        username=user.username,
        role=user.role,
        personnel_id=user.personnel_id,
        must_change_password=user.must_change_password,
    )


def require_roles(*allowed_roles: UserRole):
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="شما اجازه دسترسی به این بخش را ندارید",
            )
        return current_user

    return dependency
