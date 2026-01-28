from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    UserResponse,
    LoginResponse,
    RefreshResponse,
    ApiResponse,
)
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_email,
    get_user_by_id,
    create_user,
    authenticate_user,
)
from app.dependencies import get_current_user


router = APIRouter(tags=["Authentication"])


@router.post("/register", response_model=ApiResponse)
async def register(
    request: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register a new user account."""
    # Check if user already exists
    existing_user = await get_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create user
    user = await create_user(db, request.email, request.password, request.name)
    
    return ApiResponse(
        success=True,
        data=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            createdAt=user.created_at,
        ).model_dump(by_alias=True),
        message="Registration successful",
    )


@router.post("/login", response_model=ApiResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Login and receive JWT tokens."""
    # Authenticate user
    user = await authenticate_user(db, request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    
    return ApiResponse(
        success=True,
        data=LoginResponse(
            accessToken=access_token,
            refreshToken=refresh_token,
            user=UserResponse(
                id=user.id,
                email=user.email,
                name=user.name,
                createdAt=user.created_at,
            ),
        ).model_dump(by_alias=True),
    )


@router.post("/logout", response_model=ApiResponse)
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Logout the current user."""
    # In a more complete implementation, you would invalidate the token
    # by adding it to a blacklist in Redis. For now, we just return success.
    return ApiResponse(
        success=True,
        message="Logged out successfully",
    )


@router.post("/refresh", response_model=ApiResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Refresh the access token using a refresh token."""
    # Decode refresh token
    payload = decode_token(request.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    
    # Check token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    
    # Get user ID
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )
    
    # Verify user exists
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    # Create new access token
    new_access_token = create_access_token(user.id)
    
    return ApiResponse(
        success=True,
        data=RefreshResponse(accessToken=new_access_token).model_dump(by_alias=True),
    )


@router.get("/me", response_model=ApiResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get the current authenticated user."""
    return ApiResponse(
        success=True,
        data=UserResponse(
            id=current_user.id,
            email=current_user.email,
            name=current_user.name,
            createdAt=current_user.created_at,
        ).model_dump(by_alias=True),
    )
