# Security Middleware
import re
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from config.settings import settings
from app.auth_service import auth_service
from app.rate_limit_service import rate_limit_service
from app.auth_models import SecurityEvent, QueryValidation
import logging

logger = logging.getLogger(__name__)

class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.security_events = []  # In-memory storage (replace with database)
        
    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch"""
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        # Add request ID to request state
        request.state.request_id = request_id
        
        try:
            # Extract client information
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            
            # Log security event
            await self._log_security_event(
                event_type="request_start",
                request_id=request_id,
                user_id=None,
                event_data={"path": request.url.path, "method": request.method},
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            # Apply security checks
            response = await self._apply_security_checks(request, call_next)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log completion
            await self._log_security_event(
                event_type="request_complete",
                request_id=request_id,
                user_id=getattr(request.state, 'user_id', None),
                event_data={
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "processing_time": processing_time
                },
                ip_address=client_ip,
                user_agent=user_agent
            )
            
            return response
            
        except HTTPException as e:
            # Log security violations
            await self._log_security_event(
                event_type="security_violation",
                request_id=request_id,
                user_id=getattr(request.state, 'user_id', None),
                event_data={
                    "error": str(e.detail),
                    "status_code": e.status_code,
                    "path": request.url.path
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.headers.get("user-agent", "")
            )
            raise e
        except Exception as e:
            logger.error(f"Security middleware error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal security error"
            )
    
    async def _apply_security_checks(self, request: Request, call_next):
        """Apply all security checks"""
        
        # Skip authentication for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # 1. Authentication check for protected endpoints
        if self._is_protected_endpoint(request.url.path):
            user = await self._authenticate_request(request)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            request.state.user = user
            request.state.user_id = user["user_id"]
        
        # 2. Rate limiting check
        if hasattr(request.state, 'user_id'):
            await self._check_rate_limits(request)
        
        # 3. Query validation for query endpoints
        if request.url.path == "/api/query" and request.method == "POST":
            await self._validate_query(request)
        
        # 4. Process request
        response = await call_next(request)
        
        # 5. Increment rate limits after successful request
        if hasattr(request.state, 'user_id') and response.status_code < 400:
            await self._increment_rate_limits(request)
        
        return response
    
    def _is_protected_endpoint(self, path: str) -> bool:
        """Check if endpoint requires authentication"""
        protected_paths = [
            "/api/query",
            "/api/databases/connect",
            "/api/databases/schema",
            "/api/tables",
            "/api/admin"
        ]
        
        return any(path.startswith(protected_path) for protected_path in protected_paths)
    
    async def _authenticate_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """Authenticate request using JWT token"""
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                return None
            
            # Verify token
            payload = auth_service.verify_token(token)
            if not payload:
                return None
            
            # Get user
            user_id = payload.get("user_id")
            user = auth_service.get_user_by_id(user_id)
            
            if not user or not user["is_active"]:
                return None
            
            return user
            
        except Exception as e:
            logger.warning(f"Authentication error: {str(e)}")
            return None
    
    async def _check_rate_limits(self, request: Request):
        """Check all applicable rate limits"""
        user_id = request.state.user_id
        endpoint = request.url.path
        
        # Check user rate limits
        user_allowed, user_info = rate_limit_service.check_user_rate_limit(user_id)
        if not user_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"User rate limit exceeded: {user_info['exceeded_window']}",
                headers={"Retry-After": str(user_info['retry_after'])}
            )
        
        # Check endpoint rate limits
        endpoint_allowed, endpoint_info = rate_limit_service.check_endpoint_rate_limit(user_id, endpoint)
        if not endpoint_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Endpoint rate limit exceeded: {endpoint_info['exceeded_window']}",
                headers={"Retry-After": str(endpoint_info['retry_after'])}
            )
        
        # Check Groq API rate limits for query endpoints
        if endpoint == "/api/query":
            groq_allowed, groq_info = rate_limit_service.check_groq_rate_limit()
            if not groq_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Groq API rate limit exceeded: {groq_info['exceeded_window']}",
                    headers={"Retry-After": str(groq_info['retry_after'])}
                )
    
    async def _increment_rate_limits(self, request: Request):
        """Increment rate limit counters"""
        user_id = request.state.user_id
        endpoint = request.url.path
        
        # Increment user rate limits
        rate_limit_service.increment_user_rate_limit(user_id)
        
        # Increment endpoint rate limits
        rate_limit_service.increment_endpoint_rate_limit(user_id, endpoint)
        
        # Increment Groq API rate limits for query endpoints
        if endpoint == "/api/query":
            rate_limit_service.increment_groq_rate_limit()
    
    async def _validate_query(self, request: Request):
        """Validate SQL query for security"""
        try:
            # Get request body
            body = await request.body()
            if not body:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Request body is required"
                )
            
            import json
            data = json.loads(body)
            query = data.get("query", "")
            
            if not query:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Query is required"
                )
            
            # Validate query
            validation_result = self._validate_sql_query(query)
            if not validation_result.is_valid:
                await self._log_security_event(
                    event_type="blocked_query",
                    request_id=request.state.request_id,
                    user_id=getattr(request.state, 'user_id', None),
                    event_data={
                        "query": query,
                        "blocked_operations": validation_result.blocked_operations,
                        "blocked_patterns": validation_result.blocked_patterns,
                        "warnings": validation_result.warnings
                    },
                    ip_address=self._get_client_ip(request),
                    user_agent=request.headers.get("user-agent", "")
                )
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Query blocked: {', '.join(validation_result.blocked_operations + validation_result.blocked_patterns)}"
                )
            
            # Store sanitized query in request state
            request.state.sanitized_query = validation_result.sanitized_query
            
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in request body"
            )
    
    def _validate_sql_query(self, query: str) -> QueryValidation:
        """Validate SQL query for security threats"""
        query_upper = query.upper().strip()
        blocked_operations = []
        blocked_patterns = []
        warnings = []
        
        # Check query length
        if len(query) > settings.MAX_QUERY_LENGTH:
            warnings.append(f"Query length ({len(query)}) exceeds maximum ({settings.MAX_QUERY_LENGTH})")
        
        # Check for blocked operations
        for operation in settings.BLOCKED_OPERATIONS:
            if operation.upper() in query_upper:
                blocked_operations.append(operation)
        
        # Check for blocked patterns
        for pattern in settings.BLOCKED_PATTERNS:
            if pattern.upper() in query_upper:
                blocked_patterns.append(pattern)
        
        # Check for multiple statements (potential injection)
        if ';' in query and query.count(';') > 1:
            blocked_patterns.append("Multiple statements")
        
        # Check for comment-based injection
        if '--' in query or '/*' in query:
            blocked_patterns.append("SQL comments")
        
        # Check for union-based injection
        if 'UNION' in query_upper:
            blocked_patterns.append("UNION operation")
        
        # Sanitize query (basic)
        sanitized_query = query
        if blocked_operations or blocked_patterns:
            sanitized_query = None
        
        is_valid = len(blocked_operations) == 0 and len(blocked_patterns) == 0
        
        return QueryValidation(
            query=query,
            is_valid=is_valid,
            blocked_operations=blocked_operations,
            blocked_patterns=blocked_patterns,
            warnings=warnings,
            sanitized_query=sanitized_query
        )
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        return request.client.host if request.client else "unknown"
    
    async def _log_security_event(self, event_type: str, request_id: str, 
                                 user_id: Optional[int], event_data: Dict[str, Any],
                                 ip_address: str, user_agent: str):
        """Log security event"""
        event = SecurityEvent(
            event_id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=event_type,
            event_data=event_data,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.now(),
            severity=self._get_event_severity(event_type)
        )
        
        self.security_events.append(event)
        
        # Log to logger
        logger.info(f"Security event: {event_type} - User: {user_id}, IP: {ip_address}")
        
        # Keep only last 1000 events in memory
        if len(self.security_events) > 1000:
            self.security_events = self.security_events[-1000:]
    
    def _get_event_severity(self, event_type: str) -> str:
        """Get severity level for event type"""
        severity_map = {
            "request_start": "low",
            "request_complete": "low",
            "security_violation": "high",
            "blocked_query": "medium",
            "rate_limit_exceeded": "medium",
            "authentication_failed": "medium",
            "suspicious_activity": "high"
        }
        return severity_map.get(event_type, "low")
    
    def get_security_events(self, limit: int = 100) -> List[SecurityEvent]:
        """Get recent security events"""
        return self.security_events[-limit:]
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        now = datetime.now()
        today_events = [e for e in self.security_events if e.timestamp.date() == now.date()]
        
        stats = {
            "total_events_today": len(today_events),
            "blocked_queries_today": len([e for e in today_events if e.event_type == "blocked_query"]),
            "rate_limit_violations_today": len([e for e in today_events if e.event_type == "rate_limit_exceeded"]),
            "failed_logins_today": len([e for e in today_events if e.event_type == "authentication_failed"]),
            "security_violations_today": len([e for e in today_events if e.event_type == "security_violation"]),
            "top_blocked_operations": self._get_top_blocked_operations(today_events),
            "top_blocked_patterns": self._get_top_blocked_patterns(today_events)
        }
        
        return stats
    
    def _get_top_blocked_operations(self, events: List[SecurityEvent]) -> List[Dict[str, Any]]:
        """Get top blocked operations"""
        operations = {}
        for event in events:
            if event.event_type == "blocked_query":
                for op in event.event_data.get("blocked_operations", []):
                    operations[op] = operations.get(op, 0) + 1
        
        return [{"operation": op, "count": count} for op, count in sorted(operations.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    def _get_top_blocked_patterns(self, events: List[SecurityEvent]) -> List[Dict[str, Any]]:
        """Get top blocked patterns"""
        patterns = {}
        for event in events:
            if event.event_type == "blocked_query":
                for pattern in event.event_data.get("blocked_patterns", []):
                    patterns[pattern] = patterns.get(pattern, 0) + 1
        
        return [{"pattern": pattern, "count": count} for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:5]]
