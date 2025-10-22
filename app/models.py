# Data Models for SQL AI Agent
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

class QueryType(Enum):
    SELECT = "SELECT"
    AGGREGATE = "AGGREGATE"
    JOIN = "JOIN"
    COMPLEX = "COMPLEX"

class DatabaseConfig(BaseModel):
    connection_string: str
    name: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None

class QueryRequest(BaseModel):
    query: str
    limit: Optional[int] = 100
    database_name: Optional[str] = None

class QueryResponse(BaseModel):
    success: bool
    query: str
    sql_query: Optional[str] = None
    result: Optional[Any] = None
    nlp_response: Optional[str] = None
    relevant_tables: Optional[List[str]] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None

class TableInfo(BaseModel):
    table_name: str
    database_name: str
    columns: List[Dict[str, Any]]
    row_count: Optional[int] = None
    description: Optional[str] = None

class DatabaseSchema(BaseModel):
    database_name: str
    tables: List[TableInfo]
    total_tables: int
    total_columns: int

class HealthStatus(BaseModel):
    status: str
    database_connected: bool
    llm_configured: bool
    vector_store_ready: bool
    uptime: Optional[float] = None
    version: str = "1.0.0"
