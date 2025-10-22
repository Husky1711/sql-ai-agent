# Authentication and Security Models
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    user_id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

class TokenRefresh(BaseModel):
    refresh_token: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None

# Rate Limiting Models
class RateLimitInfo(BaseModel):
    endpoint: str
    limit_per_minute: int
    limit_per_hour: int
    limit_per_day: int
    current_usage_minute: int
    current_usage_hour: int
    current_usage_day: int
    reset_time_minute: datetime
    reset_time_hour: datetime
    reset_time_day: datetime

class RateLimitResponse(BaseModel):
    success: bool
    message: str
    rate_limit_info: Optional[RateLimitInfo] = None
    retry_after: Optional[int] = None  # seconds

# Security Models
class SecurityEvent(BaseModel):
    event_id: str
    user_id: Optional[int] = None
    event_type: str  # login, query, rate_limit, blocked_query
    event_data: dict
    ip_address: str
    user_agent: str
    timestamp: datetime
    severity: str  # low, medium, high, critical

class QueryValidation(BaseModel):
    query: str
    is_valid: bool
    blocked_operations: List[str] = []
    blocked_patterns: List[str] = []
    warnings: List[str] = []
    sanitized_query: Optional[str] = None

class SecurityStats(BaseModel):
    total_queries_today: int
    blocked_queries_today: int
    rate_limit_violations_today: int
    failed_login_attempts_today: int
    active_users_today: int
    top_blocked_operations: List[dict]
    top_blocked_patterns: List[dict]

# Admin Models
class AdminUserList(BaseModel):
    users: List[UserResponse]
    total_count: int
    page: int
    page_size: int

class AdminSecurityDashboard(BaseModel):
    security_stats: SecurityStats
    recent_events: List[SecurityEvent]
    rate_limit_status: List[RateLimitInfo]
    system_health: dict
