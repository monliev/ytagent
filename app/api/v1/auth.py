from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.api.deps import get_db, get_current_user
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse

logger = structlog.get_logger()
router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Log in user and return JWT access token."""
    logger.info("auth_login_attempt", username=payload.username)
    
    # Query by username or telegram_id (if username is digits)
    stmt = select(User).where(User.username == payload.username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user and payload.username.isdigit():
        stmt = select(User).where(User.telegram_id == int(payload.username))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

    if not user:
        logger.warning("auth_login_failed_user_not_found", username=payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/Telegram ID or password",
        )
    
    # Auto-seed/upgrade password logic: if hashed_password is not set, allow transition with 'admin123'
    if not user.hashed_password:
        if payload.password == "admin123":
            from app.core.security import hash_password
            user.hashed_password = hash_password(payload.password)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info("auth_login_password_initialized", username=payload.username)
        else:
            logger.warning("auth_login_failed_uninitialized_password", username=payload.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username/Telegram ID or password",
            )
    elif not verify_password(payload.password, user.hashed_password):
        logger.warning("auth_login_failed_invalid_password", username=payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/Telegram ID or password",
        )

    if not user.is_active:
        logger.warning("auth_login_failed_inactive_user", username=payload.username)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    access_token = create_access_token(subject=user.id)
    logger.info("auth_login_success", username=payload.username, user_id=user.id)
    return TokenResponse(access_token=access_token)

@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
) -> UserResponse:
    """Retrieve the current logged-in user profile."""
    return current_user
