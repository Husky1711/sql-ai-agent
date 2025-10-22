# Global Configuration Settings
from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    # Database Configuration
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USERNAME: str = "root"
    MYSQL_PASSWORD: str = ""  # Set via environment variable
    MYSQL_DATABASE: str = ""
    MYSQL_CONNECTION_STRING: str = ""  # Will be constructed from other variables
    
    # Groq API Configuration
    GROQ_API_KEY: str = ""  # Set via environment variable
    GROQ_MODEL: str = "llama-3.1-8b-instant"  # Updated to current model
    
    # Production Embedding Storage Configuration
    EMBEDDING_STORAGE_DIR: str = "./embeddings_storage"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_SIMILARITY_THRESHOLD: float = 0.3
    EMBEDDING_CACHE_TTL: int = 3600  # 1 hour
    
    # Legacy ChromaDB Configuration (deprecated)
    VECTOR_STORE_TYPE: str = "production"  # Changed from "chroma"
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_db"  # Keep for backward compatibility
    
    # LangChain Configuration
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "sql-agent-poc"
    
    # Application Configuration
    APP_NAME: str = "SQL AI Agent POC"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Performance Configuration
    MAX_QUERY_LENGTH: int = 1000
    MAX_RESULTS_LIMIT: int = 1000
    QUERY_TIMEOUT: int = 30
    CACHE_TTL: int = 3600  # 1 hour
    
    # Security Configuration
    SECRET_KEY: str = ""  # Set via environment variable
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Rate Limiting Configuration
    RATE_LIMIT_REDIS_URL: str = "redis://localhost:6379"
    RATE_LIMIT_ENABLED: bool = True
    
    # Per-user rate limits
    USER_QUERY_LIMIT_PER_MINUTE: int = 10
    USER_QUERY_LIMIT_PER_HOUR: int = 100
    USER_QUERY_LIMIT_PER_DAY: int = 1000
    
    # Per-endpoint rate limits
    ENDPOINT_RATE_LIMITS: dict = {
        "/api/query": {"per_minute": 5, "per_hour": 50},
        "/api/databases/connect": {"per_minute": 2, "per_hour": 10},
        "/api/databases/schema": {"per_minute": 10, "per_hour": 100}
    }
    
    # Groq API protection
    GROQ_RATE_LIMIT_PER_MINUTE: int = 20
    GROQ_RATE_LIMIT_PER_HOUR: int = 200
    GROQ_RATE_LIMIT_PER_DAY: int = 2000
    
    # SQL Security Rules
    ALLOWED_OPERATIONS: list = ["SELECT", "SHOW", "DESCRIBE", "EXPLAIN"]
    BLOCKED_OPERATIONS: list = ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE"]
    BLOCKED_PATTERNS: list = ["UNION", "INFORMATION_SCHEMA", "SYSTEM", "EXEC", "SP_"]
    MAX_QUERY_LENGTH: int = 1000
    MAX_RESULT_ROWS: int = 1000
    QUERY_TIMEOUT_SECONDS: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Global settings instance
settings = Settings()
