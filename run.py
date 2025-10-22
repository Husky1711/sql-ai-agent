# SQL AI Agent POC Runner
import asyncio
import uvicorn
from app.main import app
from config.settings import settings

if __name__ == "__main__":
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"📊 Database: {settings.MYSQL_CONNECTION_STRING}")
    print(f"🤖 LLM: {settings.GROQ_MODEL}")
    print(f"🔍 Vector Store: {settings.VECTOR_STORE_TYPE}")
    print(f"🌐 Server: http://localhost:8000")
    print(f"📚 API Docs: http://localhost:8000/docs")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
