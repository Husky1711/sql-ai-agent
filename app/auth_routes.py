# Authentication API Endpoints
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

from app.auth_service import auth_service
from app.auth_models import (
    UserCreate, UserLogin, UserResponse, TokenResponse, TokenRefresh,
    PasswordChange, UserUpdate, RateLimitInfo, SecurityStats
)
from app.security_middleware import SecurityMiddleware
from config.settings import settings

logger = logging.getLogger(__name__)

# Create router
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Security scheme
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("user_id")
    user = auth_service.get_user_by_id(user_id)
    
    if not user or not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user

def get_admin_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Get current admin user"""
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

@auth_router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate):
    """Register a new user"""
    try:
        user = auth_service.register_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name,
            role=user_data.role
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists"
            )
        
        # Return user without password hash
        return UserResponse(
            user_id=user["user_id"],
            username=user["username"],
            email=user["email"],
            full_name=user["full_name"],
            role=user["role"],
            is_active=user["is_active"],
            created_at=user["created_at"],
            last_login=user["last_login"]
        )
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@auth_router.post("/login", response_model=TokenResponse)
async def login_user(login_data: UserLogin):
    """Login user and return access tokens"""
    try:
        user = auth_service.authenticate_user(login_data.username, login_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Create tokens
        token_data = {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": user["role"]
        }
        
        access_token = auth_service.create_access_token(token_data)
        refresh_token = auth_service.create_refresh_token(token_data)
        
        # Store refresh token
        auth_service.store_refresh_token(refresh_token, user["user_id"])
        
        logger.info(f"User logged in: {user['username']}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(token_data: TokenRefresh):
    """Refresh access token using refresh token"""
    try:
        user_id = auth_service.validate_refresh_token(token_data.refresh_token)
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        user = auth_service.get_user_by_id(user_id)
        if not user or not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new tokens
        token_data_dict = {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": user["role"]
        }
        
        access_token = auth_service.create_access_token(token_data_dict)
        refresh_token = auth_service.create_refresh_token(token_data_dict)
        
        # Store new refresh token and revoke old one
        auth_service.revoke_refresh_token(token_data.refresh_token)
        auth_service.store_refresh_token(refresh_token, user["user_id"])
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@auth_router.post("/logout")
async def logout_user(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Logout user (invalidate refresh token)"""
    try:
        # In a real implementation, you would invalidate the token
        # For now, we'll just log the logout
        logger.info(f"User logged out: {current_user['username']}")
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
        last_login=current_user["last_login"]
    )

@auth_router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update current user information"""
    try:
        updated_user = auth_service.update_user(
            current_user["user_id"],
            full_name=user_update.full_name,
            email=user_update.email
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user"
            )
        
        return UserResponse(
            user_id=updated_user["user_id"],
            username=updated_user["username"],
            email=updated_user["email"],
            full_name=updated_user["full_name"],
            role=updated_user["role"],
            is_active=updated_user["is_active"],
            created_at=updated_user["created_at"],
            last_login=updated_user["last_login"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed"
        )

@auth_router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Change user password"""
    try:
        success = auth_service.change_password(
            current_user["user_id"],
            password_data.current_password,
            password_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid current password"
            )
        
        logger.info(f"Password changed for user: {current_user['username']}")
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

# Admin endpoints
@auth_router.get("/admin/users", response_model=List[UserResponse])
async def list_all_users(admin_user: Dict[str, Any] = Depends(get_admin_user)):
    """List all users (admin only)"""
    try:
        users = auth_service.get_all_users()
        
        return [
            UserResponse(
                user_id=user["user_id"],
                username=user["username"],
                email=user["email"],
                full_name=user["full_name"],
                role=user["role"],
                is_active=user["is_active"],
                created_at=user["created_at"],
                last_login=user["last_login"]
            )
            for user in users
        ]
        
    except Exception as e:
        logger.error(f"List users error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )

@auth_router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Delete user (admin only)"""
    try:
        # Prevent admin from deleting themselves
        if user_id == admin_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        success = auth_service.delete_user(user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User {user_id} deleted by admin {admin_user['username']}")
        return {"message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )

@auth_router.put("/admin/users/{user_id}/activate")
async def toggle_user_status(
    user_id: int,
    admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """Toggle user active status (admin only)"""
    try:
        user = auth_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent admin from deactivating themselves
        if user_id == admin_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own status"
            )
        
        updated_user = auth_service.update_user(user_id, is_active=not user["is_active"])
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user status"
            )
        
        status_text = "activated" if updated_user["is_active"] else "deactivated"
        logger.info(f"User {user_id} {status_text} by admin {admin_user['username']}")
        
        return {"message": f"User {status_text} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle user status error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user status"
        )
