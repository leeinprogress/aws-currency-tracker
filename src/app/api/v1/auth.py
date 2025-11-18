"""
Authentication API endpoints
"""
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.dependencies import get_user_repository_dependency
from app.db.repositories import UserRepository
from app.core.security import create_access_token
from app.core.config import settings
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserResponse, TokenResponse

router = APIRouter()


def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository_dependency)
) -> UserService:
    """Dependency to get user service"""
    return UserService(user_repository)


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_data: UserCreate,
    service: UserService = Depends(get_user_service),
):
    """Register a new user"""
    try:
        user = await service.create_user(user_data)
        return UserResponse(**user.to_dict())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: UserService = Depends(get_user_service),
):
    """Login and get access token"""
    user = await service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.user_id, "email": user.email},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(**user.to_dict())
    )

