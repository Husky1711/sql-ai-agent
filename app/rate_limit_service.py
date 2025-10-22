# Rate Limiting Service
import redis
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

class RateLimitService:
    """Handles rate limiting for users and endpoints"""
    
    def __init__(self):
        self.redis_client = None
        self.enabled = settings.RATE_LIMIT_ENABLED
        
        # Rate limit configurations
        self.user_limits = {
            "per_minute": settings.USER_QUERY_LIMIT_PER_MINUTE,
            "per_hour": settings.USER_QUERY_LIMIT_PER_HOUR,
            "per_day": settings.USER_QUERY_LIMIT_PER_DAY
        }
        
        self.endpoint_limits = settings.ENDPOINT_RATE_LIMITS
        
        self.groq_limits = {
            "per_minute": settings.GROQ_RATE_LIMIT_PER_MINUTE,
            "per_hour": settings.GROQ_RATE_LIMIT_PER_HOUR,
            "per_day": settings.GROQ_RATE_LIMIT_PER_DAY
        }
        
        # Initialize Redis connection
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            if self.enabled:
                self.redis_client = redis.from_url(settings.RATE_LIMIT_REDIS_URL)
                # Test connection
                self.redis_client.ping()
                logger.info("Redis connection established for rate limiting")
            else:
                logger.info("Rate limiting disabled")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            logger.warning("Rate limiting will use in-memory storage")
            self.redis_client = None
    
    def _get_key(self, prefix: str, identifier: str, window: str) -> str:
        """Generate Redis key for rate limiting"""
        return f"rate_limit:{prefix}:{identifier}:{window}"
    
    def _get_current_window(self, window_type: str) -> Tuple[int, int]:
        """Get current time window boundaries"""
        now = int(time.time())
        
        if window_type == "per_minute" or window_type == "minute":
            window_start = (now // 60) * 60
            window_end = window_start + 60
        elif window_type == "per_hour" or window_type == "hour":
            window_start = (now // 3600) * 3600
            window_end = window_start + 3600
        elif window_type == "per_day" or window_type == "day":
            window_start = (now // 86400) * 86400
            window_end = window_start + 86400
        else:
            raise ValueError(f"Invalid window type: {window_type}")
        
        return window_start, window_end
    
    def _increment_counter(self, key: str, window_start: int, window_end: int) -> int:
        """Increment counter in Redis or memory"""
        if self.redis_client:
            try:
                # Use Redis pipeline for atomic operations
                pipe = self.redis_client.pipeline()
                pipe.incr(key)
                pipe.expireat(key, window_end)
                results = pipe.execute()
                return results[0]
            except Exception as e:
                logger.error(f"Redis error: {str(e)}")
                # Fallback to memory
                return self._increment_memory_counter(key, window_start, window_end)
        else:
            return self._increment_memory_counter(key, window_start, window_end)
    
    def _increment_memory_counter(self, key: str, window_start: int, window_end: int) -> int:
        """Increment counter in memory (fallback)"""
        if not hasattr(self, '_memory_counters'):
            self._memory_counters = {}
        
        if key not in self._memory_counters:
            self._memory_counters[key] = {"count": 0, "window_end": window_end}
        
        counter = self._memory_counters[key]
        
        # Check if window has expired
        if time.time() >= counter["window_end"]:
            counter["count"] = 1
            counter["window_end"] = window_end
        else:
            counter["count"] += 1
        
        return counter["count"]
    
    def _get_counter(self, key: str) -> int:
        """Get current counter value"""
        if self.redis_client:
            try:
                return int(self.redis_client.get(key) or 0)
            except Exception as e:
                logger.error(f"Redis error: {str(e)}")
                return self._get_memory_counter(key)
        else:
            return self._get_memory_counter(key)
    
    def _get_memory_counter(self, key: str) -> int:
        """Get counter from memory"""
        if not hasattr(self, '_memory_counters'):
            return 0
        
        counter = self._memory_counters.get(key)
        if not counter:
            return 0
        
        # Check if window has expired
        if time.time() >= counter["window_end"]:
            return 0
        
        return counter["count"]
    
    def check_user_rate_limit(self, user_id: int) -> Tuple[bool, Dict[str, Any]]:
        """Check if user has exceeded rate limits"""
        if not self.enabled:
            return True, {}
        
        user_limits_info = {}
        
        for window_type, limit in self.user_limits.items():
            key = self._get_key("user", str(user_id), window_type)
            window_start, window_end = self._get_current_window(window_type)
            
            current_count = self._get_counter(key)
            
            user_limits_info[window_type] = {
                "limit": limit,
                "current": current_count,
                "remaining": max(0, limit - current_count),
                "reset_time": window_end
            }
            
            if current_count >= limit:
                logger.warning(f"User {user_id} exceeded {window_type} rate limit: {current_count}/{limit}")
                return False, {
                    "exceeded_window": window_type,
                    "limit": limit,
                    "current": current_count,
                    "retry_after": window_end - int(time.time()),
                    "limits_info": user_limits_info
                }
        
        return True, {"limits_info": user_limits_info}
    
    def increment_user_rate_limit(self, user_id: int) -> Dict[str, Any]:
        """Increment user rate limit counters"""
        if not self.enabled:
            return {}
        
        limits_info = {}
        
        for window_type, limit in self.user_limits.items():
            key = self._get_key("user", str(user_id), window_type)
            window_start, window_end = self._get_current_window(window_type)
            
            current_count = self._increment_counter(key, window_start, window_end)
            
            limits_info[window_type] = {
                "limit": limit,
                "current": current_count,
                "remaining": max(0, limit - current_count),
                "reset_time": window_end
            }
        
        return limits_info
    
    def check_endpoint_rate_limit(self, user_id: int, endpoint: str) -> Tuple[bool, Dict[str, Any]]:
        """Check if user has exceeded endpoint-specific rate limits"""
        if not self.enabled or endpoint not in self.endpoint_limits:
            return True, {}
        
        endpoint_limits = self.endpoint_limits[endpoint]
        limits_info = {}
        
        for window_type, limit in endpoint_limits.items():
            key = self._get_key("endpoint", f"{user_id}:{endpoint}", window_type)
            window_start, window_end = self._get_current_window(window_type)
            
            current_count = self._get_counter(key)
            
            limits_info[window_type] = {
                "limit": limit,
                "current": current_count,
                "remaining": max(0, limit - current_count),
                "reset_time": window_end
            }
            
            if current_count >= limit:
                logger.warning(f"User {user_id} exceeded {endpoint} {window_type} rate limit: {current_count}/{limit}")
                return False, {
                    "exceeded_window": window_type,
                    "limit": limit,
                    "current": current_count,
                    "retry_after": window_end - int(time.time()),
                    "limits_info": limits_info
                }
        
        return True, {"limits_info": limits_info}
    
    def increment_endpoint_rate_limit(self, user_id: int, endpoint: str) -> Dict[str, Any]:
        """Increment endpoint rate limit counters"""
        if not self.enabled or endpoint not in self.endpoint_limits:
            return {}
        
        endpoint_limits = self.endpoint_limits[endpoint]
        limits_info = {}
        
        for window_type, limit in endpoint_limits.items():
            key = self._get_key("endpoint", f"{user_id}:{endpoint}", window_type)
            window_start, window_end = self._get_current_window(window_type)
            
            current_count = self._increment_counter(key, window_start, window_end)
            
            limits_info[window_type] = {
                "limit": limit,
                "current": current_count,
                "remaining": max(0, limit - current_count),
                "reset_time": window_end
            }
        
        return limits_info
    
    def check_groq_rate_limit(self) -> Tuple[bool, Dict[str, Any]]:
        """Check if Groq API rate limits are exceeded"""
        if not self.enabled:
            return True, {}
        
        limits_info = {}
        
        for window_type, limit in self.groq_limits.items():
            key = self._get_key("groq", "global", window_type)
            window_start, window_end = self._get_current_window(window_type)
            
            current_count = self._get_counter(key)
            
            limits_info[window_type] = {
                "limit": limit,
                "current": current_count,
                "remaining": max(0, limit - current_count),
                "reset_time": window_end
            }
            
            if current_count >= limit:
                logger.warning(f"Groq API exceeded {window_type} rate limit: {current_count}/{limit}")
                return False, {
                    "exceeded_window": window_type,
                    "limit": limit,
                    "current": current_count,
                    "retry_after": window_end - int(time.time()),
                    "limits_info": limits_info
                }
        
        return True, {"limits_info": limits_info}
    
    def increment_groq_rate_limit(self) -> Dict[str, Any]:
        """Increment Groq API rate limit counters"""
        if not self.enabled:
            return {}
        
        limits_info = {}
        
        for window_type, limit in self.groq_limits.items():
            key = self._get_key("groq", "global", window_type)
            window_start, window_end = self._get_current_window(window_type)
            
            current_count = self._increment_counter(key, window_start, window_end)
            
            limits_info[window_type] = {
                "limit": limit,
                "current": current_count,
                "remaining": max(0, limit - current_count),
                "reset_time": window_end
            }
        
        return limits_info
    
    def get_rate_limit_status(self, user_id: int, endpoint: str = None) -> Dict[str, Any]:
        """Get comprehensive rate limit status for user"""
        status = {
            "user_limits": {},
            "endpoint_limits": {},
            "groq_limits": {}
        }
        
        # User limits
        _, user_info = self.check_user_rate_limit(user_id)
        status["user_limits"] = user_info.get("limits_info", {})
        
        # Endpoint limits
        if endpoint:
            _, endpoint_info = self.check_endpoint_rate_limit(user_id, endpoint)
            status["endpoint_limits"] = endpoint_info.get("limits_info", {})
        
        # Groq limits
        _, groq_info = self.check_groq_rate_limit()
        status["groq_limits"] = groq_info.get("limits_info", {})
        
        return status
    
    def reset_rate_limits(self, user_id: int = None, endpoint: str = None) -> bool:
        """Reset rate limits (admin function)"""
        try:
            if self.redis_client:
                if user_id:
                    # Reset user limits
                    for window_type in ["per_minute", "per_hour", "per_day"]:
                        key = self._get_key("user", str(user_id), window_type)
                        self.redis_client.delete(key)
                
                if endpoint:
                    # Reset endpoint limits for all users
                    pattern = f"rate_limit:endpoint:*:{endpoint}:*"
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
                
                logger.info(f"Rate limits reset for user={user_id}, endpoint={endpoint}")
                return True
            else:
                # Reset memory counters
                if hasattr(self, '_memory_counters'):
                    if user_id:
                        keys_to_delete = [k for k in self._memory_counters.keys() if f"user:{user_id}" in k]
                        for key in keys_to_delete:
                            del self._memory_counters[key]
                    
                    if endpoint:
                        keys_to_delete = [k for k in self._memory_counters.keys() if f"endpoint:{endpoint}" in k]
                        for key in keys_to_delete:
                            del self._memory_counters[key]
                
                logger.info(f"Memory rate limits reset for user={user_id}, endpoint={endpoint}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to reset rate limits: {str(e)}")
            return False

# Global rate limiting service instance
rate_limit_service = RateLimitService()
