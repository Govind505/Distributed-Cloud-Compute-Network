import uuid
from typing import Callable, Iterable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.utils.auth import decode_access_token

security = HTTPBearer(auto_error=True)
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer JWT token and return active authenticated user."""
    token = credentials.credentials
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or malformed authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or pending verification",
        )
    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Optionally resolve authenticated user if token is provided."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_roles(*allowed_roles: UserRole | str) -> Callable:
    """Enforce that current user possesses at least one of the specified roles."""
    normalized = []
    for r in allowed_roles:
        if isinstance(r, UserRole):
            normalized.append(r)
        else:
            try:
                normalized.append(UserRole(r))
            except ValueError:
                pass

    async def _role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in normalized and current_user.role != UserRole.ADMIN:
            allowed_names = [r.value for r in normalized]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Requires role in {allowed_names}. Current role: '{current_user.role.value}'",
            )
        return current_user

    return _role_checker


async def require_client(current_user: User = Depends(get_current_user)) -> User:
    """Allow compute clients or administrators."""
    if current_user.role not in (UserRole.COMPUTE_USER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compute client access required. Providers cannot submit or manage client workloads.",
        )
    return current_user


async def require_provider(current_user: User = Depends(get_current_user)) -> User:
    """Allow compute providers or administrators."""
    if current_user.role not in (UserRole.COMPUTE_PROVIDER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compute provider access required. Enrolling host machines is reserved for providers.",
        )
    return current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Allow administrator only."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required for governance and cluster configuration.",
        )
    return current_user
