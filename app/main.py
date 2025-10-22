# FastAPI Application for SQL AI Agent
from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import time
import os
from app.sql_agent import SQLAgent
from app.models import (
    DatabaseConfig, QueryRequest, QueryResponse, 
    DatabaseSchema, HealthStatus, TableInfo
)
from app.auth_routes import auth_router
from app.security_middleware import SecurityMiddleware
from config.settings import settings
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SQL AI Agent POC using LangChain and Groq"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security middleware
app.add_middleware(SecurityMiddleware)

# Global SQL Agent instance
sql_agent = SQLAgent()

# Include authentication router
app.include_router(auth_router)

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize the application"""
    try:
        logger.info("🚀 Starting SQL AI Agent POC...")
        logger.info(f"📊 Database: {settings.MYSQL_CONNECTION_STRING}")
        logger.info(f"🤖 LLM: {settings.GROQ_MODEL}")
        logger.info(f"🔍 Vector Store: {settings.VECTOR_STORE_TYPE}")
        
        # Note: We'll connect to database when user provides connection details
        logger.info("✅ Application started successfully")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {str(e)}")
        raise

# Add static file serving
app.mount("/static", StaticFiles(directory="."), name="static")

# Serve HTML files
@app.get("/{filename}.html")
async def serve_html(filename: str):
    """Serve HTML files"""
    file_path = f"{filename}.html"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "SQL AI Agent POC",
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs"
    }

# Database management endpoints
@app.post("/api/databases/connect")
async def connect_database(config: DatabaseConfig):
    """Connect to a MySQL database"""
    try:
        success = await sql_agent.connect_database(
            config.connection_string, 
            config.name
        )
        
        if success:
            return {
                "success": True,
                "message": f"Connected to database: {config.name}",
                "connection_string": config.connection_string
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to connect to database")
            
    except Exception as e:
        logger.error(f"❌ Database connection error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/databases/schema")
async def get_database_schema():
    """Get current database schema"""
    try:
        schema_info = sql_agent.get_database_schema()
        
        if "error" in schema_info:
            raise HTTPException(status_code=400, detail=schema_info["error"])
        
        return schema_info
        
    except Exception as e:
        logger.error(f"❌ Schema retrieval error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tables")
async def list_tables():
    """List all tables in the database"""
    try:
        schema_info = sql_agent.get_database_schema()
        
        if "error" in schema_info:
            raise HTTPException(status_code=400, detail=schema_info["error"])
        
        return {"tables": schema_info["tables"]}
        
    except Exception as e:
        logger.error(f"❌ Table listing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tables/{table_name}/columns")
async def list_table_columns(table_name: str):
    """List columns in a specific table"""
    try:
        if not sql_agent.sql_database:
            raise HTTPException(status_code=400, detail="No database connected")
        
        # Get table info
        table_info = sql_agent.sql_database.get_table_info([table_name])
        
        return {
            "table_name": table_name,
            "table_info": table_info
        }
        
    except Exception as e:
        logger.error(f"❌ Column listing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Query execution endpoints
@app.post("/api/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """Execute natural language query"""
    try:
        start_time = time.time()
        
        result = await sql_agent.process_query(request.query)
        
        return QueryResponse(
            success=result["success"],
            query=result["query"],
            sql_query=result.get("sql_query"),
            result=result.get("result"),
            nlp_response=result.get("nlp_response"),
            relevant_tables=result.get("relevant_tables"),
            execution_time=result.get("execution_time"),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"❌ Query execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Health and monitoring endpoints
@app.get("/api/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint"""
    try:
        health_status = sql_agent.get_health_status()
        
        return HealthStatus(
            status="healthy" if health_status["database_connected"] else "degraded",
            database_connected=health_status["database_connected"],
            llm_configured=health_status["llm_configured"],
            vector_store_ready=health_status.get("embedding_storage", {}).get("status") == "healthy",
            version=settings.APP_VERSION
        )
        
    except Exception as e:
        logger.error(f"❌ Health check error: {str(e)}")
        return HealthStatus(
            status="unhealthy",
            database_connected=False,
            llm_configured=False,
            vector_store_ready=False,
            version=settings.APP_VERSION
        )

# Test endpoints for development
@app.get("/api/test/sample-queries")
async def get_sample_queries():
    """Get sample queries for testing"""
    return {
        "simple_queries": [
            "Show me all users",
            "List all products",
            "Get customer names",
            "Count total orders"
        ],
        "filtered_queries": [
            "Show users with age greater than 25",
            "List products with price less than 100",
            "Get orders from last month"
        ],
        "join_queries": [
            "Show customers and their orders",
            "List products with their categories",
            "Get users with their order history"
        ],
        "aggregation_queries": [
            "Count total users",
            "Sum of all order amounts",
            "Average product price",
            "Top 10 customers by total spending"
        ]
    }

# WebSocket endpoint for streaming responses
@app.websocket("/ws/query")
async def websocket_query(websocket: WebSocket):
    """WebSocket endpoint for streaming query responses"""
    await websocket.accept()
    
    try:
        while True:
            # Receive query from client
            data = await websocket.receive_json()
            query = data.get("query")
            token = data.get("token")  # Get auth token from client
            
            if not query:
                await websocket.send_json({"type": "error", "error": "No query provided"})
                continue
            
            # Verify authentication if token provided
            if token:
                try:
                    # Simple token validation (you can enhance this)
                    import jwt
                    from config.settings import settings
                    jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                except:
                    await websocket.send_json({"type": "error", "error": "Invalid authentication token"})
                    continue
            
            # Send initial status
            await websocket.send_json({
                "type": "status",
                "message": "Processing your query...",
                "step": "analyzing"
            })
            
            try:
                # Process query step by step
                await websocket.send_json({
                    "type": "status", 
                    "message": "Finding relevant tables...",
                    "step": "tables"
                })
                
                # Find relevant tables
                relevant_tables = await sql_agent.find_relevant_tables(query)
                
                await websocket.send_json({
                    "type": "status",
                    "message": "Generating SQL query...",
                    "step": "sql_generation"
                })
                
                # Generate SQL
                sql_query = await sql_agent.generate_sql_with_groq(query)
                
                await websocket.send_json({
                    "type": "sql_generated",
                    "sql_query": sql_query
                })
                
                await websocket.send_json({
                    "type": "status",
                    "message": "Executing query...",
                    "step": "execution"
                })
                
                # Execute query
                start_time = time.time()
                result = await sql_agent.execute_sql_query(sql_query)
                execution_time = time.time() - start_time
                
                await websocket.send_json({
                    "type": "query_executed",
                    "result": result,
                    "execution_time": execution_time
                })
                
                await websocket.send_json({
                    "type": "status",
                    "message": "Generating response...",
                    "step": "nlp_response"
                })
                
                # Generate NLP response
                nlp_response = await sql_agent.generate_natural_language_response(
                    query, sql_query, result, execution_time * 1000
                )
                
                # Send final response
                await websocket.send_json({
                    "type": "complete",
                    "success": True,
                    "query": query,
                    "sql_query": sql_query,
                    "result": result,
                    "nlp_response": nlp_response,
                    "relevant_tables": relevant_tables,
                    "execution_time": execution_time
                })
                
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                    "query": query
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass

# Admin endpoints for monitoring
@app.get("/api/admin/security/stats")
async def get_security_stats():
    """Get security statistics (admin only)"""
    try:
        # Get security middleware instance
        security_middleware = None
        for middleware in app.user_middleware:
            if isinstance(middleware.cls, SecurityMiddleware):
                security_middleware = middleware
                break
        
        if not security_middleware:
            return {"message": "Security middleware not found"}
        
        stats = security_middleware.kwargs["app"].get_security_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Security stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/rate-limits")
async def get_rate_limit_status():
    """Get rate limit status (admin only)"""
    try:
        from app.rate_limit_service import rate_limit_service
        
        # Get global rate limit status
        status = {
            "enabled": rate_limit_service.enabled,
            "redis_connected": rate_limit_service.redis_client is not None,
            "user_limits": rate_limit_service.user_limits,
            "endpoint_limits": rate_limit_service.endpoint_limits,
            "groq_limits": rate_limit_service.groq_limits
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Rate limit status error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/rate-limits/reset")
async def reset_rate_limits(user_id: Optional[int] = None, endpoint: Optional[str] = None):
    """Reset rate limits (admin only)"""
    try:
        from app.rate_limit_service import rate_limit_service
        
        success = rate_limit_service.reset_rate_limits(user_id, endpoint)
        
        if success:
            return {"message": "Rate limits reset successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to reset rate limits")
        
    except Exception as e:
        logger.error(f"Reset rate limits error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
