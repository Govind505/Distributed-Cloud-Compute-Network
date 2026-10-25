from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserCreate, UserLogin, UserResponse, UserPermissions, Token
from app.utils.auth import hash_password, verify_password, create_access_token
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


def build_user_response(user: User) -> UserResponse:
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    status_val = user.status.value if hasattr(user.status, "value") else str(user.status)
    portal_map = {
        "admin": "/admin",
        "compute_provider": "/provider",
        "compute_user": "/client",
    }
    permissions = UserPermissions(
        can_submit_jobs=role_val in ("compute_user", "admin"),
        can_manage_nodes=role_val in ("compute_provider", "admin"),
        can_approve_nodes=role_val == "admin",
        can_view_audit=role_val == "admin",
        is_admin=role_val == "admin",
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        role=role_val,
        status=status_val,
        created_at=user.created_at,
        portal_url=portal_map.get(role_val, "/dashboard"),
        permissions=permissions,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user with dedicated role."""
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    try:
        role = UserRole(user_data.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {[r.value for r in UserRole]}")

    user = User(
        email=user_data.email,
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        role=role,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return build_user_response(user)


@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login and receive a JWT access token along with enriched user profile."""
    result = await db.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active or suspended",
        )
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    access_token = create_access_token(data={"sub": str(user.id), "role": role_val})
    return Token(access_token=access_token, token_type="bearer", user=build_user_response(user))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user profile, assigned role, and permissions."""
    return build_user_response(current_user)
