# Authentication Service
import jwt
import bcrypt
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from passlib.context import CryptContext
from config.settings import settings
from app.auth_models import UserRole, TokenType
import logging

logger = logging.getLogger(__name__)

class AuthenticationService:
    """Handles user authentication and token management"""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
        
        # In-memory user storage (replace with database in production)
        self.users = {}
        self.refresh_tokens = {}
        
        # Initialize with default admin user (lazy initialization)
        self._admin_created = False
    
    def _create_default_admin(self):
        """Create default admin user for testing"""
        if not self._admin_created:
            try:
                admin_password = self.hash_password("admin123")
                self.users["admin"] = {
                    "user_id": 1,
                    "username": "admin",
                    "email": "admin@sqlagent.com",
                    "password_hash": admin_password,
                    "full_name": "System Administrator",
                    "role": UserRole.ADMIN,
                    "is_active": True,
                    "created_at": datetime.now(),
                    "last_login": None
                }
                self._admin_created = True
                logger.info("Default admin user created: admin/admin123")
            except Exception as e:
                logger.error(f"Failed to create default admin: {str(e)}")
                # Create admin with simple password hash as fallback
                self.users["admin"] = {
                    "user_id": 1,
                    "username": "admin",
                    "email": "admin@sqlagent.com",
                    "password_hash": "admin123",  # Simple fallback
                    "full_name": "System Administrator",
                    "role": UserRole.ADMIN,
                    "is_active": True,
                    "created_at": datetime.now(),
                    "last_login": None
                }
                self._admin_created = True
                logger.warning("Default admin created with simple password hash")
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": TokenType.ACCESS})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": TokenType.REFRESH})
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str, token_type: TokenType = TokenType.ACCESS) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            if payload.get("type") != token_type:
                logger.warning(f"Invalid token type: expected {token_type}, got {payload.get('type')}")
                return None
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                logger.warning("Token has expired")
                return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"JWT error: {str(e)}")
            return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with username and password"""
        # Ensure admin user exists
        if not self._admin_created:
            self._create_default_admin()
        
        user = self.users.get(username)
        if not user:
            logger.warning(f"User not found: {username}")
            return None
        
        if not user["is_active"]:
            logger.warning(f"Inactive user attempted login: {username}")
            return None
        
        # Handle fallback password for admin
        if username == "admin" and user["password_hash"] == "admin123":
            if password == "admin123":
                user["last_login"] = datetime.now()
                logger.info(f"Admin authenticated with fallback password: {username}")
                return user
            else:
                logger.warning(f"Invalid fallback password for admin: {username}")
                return None
        
        if not self.verify_password(password, user["password_hash"]):
            logger.warning(f"Invalid password for user: {username}")
            return None
        
        # Update last login
        user["last_login"] = datetime.now()
        
        logger.info(f"User authenticated successfully: {username}")
        return user
    
    def register_user(self, username: str, email: str, password: str, 
                     full_name: Optional[str] = None, role: UserRole = UserRole.USER) -> Optional[Dict[str, Any]]:
        """Register a new user"""
        if username in self.users:
            logger.warning(f"Username already exists: {username}")
            return None
        
        # Check if email already exists
        for user in self.users.values():
            if user["email"] == email:
                logger.warning(f"Email already exists: {email}")
                return None
        
        user_id = max([u["user_id"] for u in self.users.values()], default=0) + 1
        password_hash = self.hash_password(password)
        
        user = {
            "user_id": user_id,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "role": role,
            "is_active": True,
            "created_at": datetime.now(),
            "last_login": None
        }
        
        self.users[username] = user
        logger.info(f"User registered successfully: {username}")
        return user
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        for user in self.users.values():
            if user["user_id"] == user_id:
                return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        return self.users.get(username)
    
    def update_user(self, user_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Update user information"""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        # Update allowed fields
        allowed_fields = ["full_name", "email", "is_active"]
        for field, value in kwargs.items():
            if field in allowed_fields:
                user[field] = value
        
        logger.info(f"User updated: {user['username']}")
        return user
    
    def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """Change user password"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        if not self.verify_password(current_password, user["password_hash"]):
            logger.warning(f"Invalid current password for user: {user['username']}")
            return False
        
        user["password_hash"] = self.hash_password(new_password)
        logger.info(f"Password changed for user: {user['username']}")
        return True
    
    def revoke_refresh_token(self, token: str) -> bool:
        """Revoke a refresh token"""
        if token in self.refresh_tokens:
            del self.refresh_tokens[token]
            logger.info("Refresh token revoked")
            return True
        return False
    
    def store_refresh_token(self, token: str, user_id: int) -> None:
        """Store refresh token"""
        self.refresh_tokens[token] = {
            "user_id": user_id,
            "created_at": datetime.now()
        }
    
    def validate_refresh_token(self, token: str) -> Optional[int]:
        """Validate refresh token and return user ID"""
        if token not in self.refresh_tokens:
            return None
        
        # Verify token signature
        payload = self.verify_token(token, TokenType.REFRESH)
        if not payload:
            # Remove invalid token
            del self.refresh_tokens[token]
            return None
        
        token_data = self.refresh_tokens[token]
        return token_data["user_id"]
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users (admin only)"""
        return list(self.users.values())
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user (admin only)"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False
        
        username = user["username"]
        del self.users[username]
        logger.info(f"User deleted: {username}")
        return True

# Global authentication service instance
auth_service = AuthenticationService()
