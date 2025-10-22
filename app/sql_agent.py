# Core SQL Agent Implementation using Groq directly
from groq import Groq
from config.settings import settings
import asyncio
import time
from typing import Dict, List, Optional, Any
import logging
import json
import pymysql
from .production_embedding_storage import ProductionEmbeddingStorage

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SQLAgent:
    def __init__(self):
        # Initialize Groq client
        self.groq_client = Groq(
            api_key=settings.GROQ_API_KEY
        )
        self.model_name = settings.GROQ_MODEL
        
        # Initialize production embedding storage
        self.embedding_storage = ProductionEmbeddingStorage()
        
        # Initialize SQL database connection
        self.db_connection = None
        self.current_database = None
        self.schema_info = {}
        
        logger.info("SQL Agent initialized successfully")
    
    async def connect_database(self, connection_string: str, database_name: str = "default"):
        """Connect to MySQL database"""
        try:
            # Parse connection string
            # Format: mysql+pymysql://username:password@host:port/database
            parts = connection_string.replace("mysql+pymysql://", "").split("/")
            auth_host = parts[0]
            database = parts[1] if len(parts) > 1 else ""
            
            auth_parts = auth_host.split("@")
            auth = auth_parts[0]
            host_port = auth_parts[1] if len(auth_parts) > 1 else "localhost:3306"
            
            # Handle URL encoding for password
            username, password = auth.split(":")
            password = password.replace("%40", "@")  # Decode @ symbol
            
            host, port = host_port.split(":")
            
            logger.info(f"Connecting to MySQL: {host}:{port}, user: {username}, database: {database}")
            
            # Connect to MySQL
            self.db_connection = pymysql.connect(
                host=host,
                port=int(port),
                user=username,
                password=password,
                database=database,
                charset='utf8mb4'
            )
            
            self.current_database = database_name
            
            # Get schema information
            await self.build_schema_info()
            
            # Build schema embeddings using production storage
            await self.build_schema_embeddings(database_name)
            
            logger.info(f"Connected to database: {database_name}")
            return True
            
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return False
    
    async def build_schema_info(self):
        """Build schema information from database"""
        try:
            cursor = self.db_connection.cursor()
            
            # Get all tables
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            
            self.schema_info = {}
            
            for table in tables:
                # Get table structure
                cursor.execute(f"DESCRIBE {table}")
                columns = cursor.fetchall()
                
                # Get sample data
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                sample_data = cursor.fetchall()
                
                self.schema_info[table] = {
                    "columns": columns,
                    "sample_data": sample_data
                }
            
            cursor.close()
            logger.info(f"Schema info built for {len(tables)} tables")
            
        except Exception as e:
            logger.error(f"Schema info build failed: {str(e)}")
    
    async def build_schema_embeddings(self, database_name: str):
        """Build embeddings for database schema using production storage"""
        try:
            # Store schema embeddings using production storage
            success = self.embedding_storage.store_schema_embeddings(database_name, self.schema_info)
            
            if success:
                logger.info(f"Schema embeddings built for {len(self.schema_info)} tables using production storage")
            else:
                logger.error("Failed to build schema embeddings")
            
        except Exception as e:
            logger.error(f"Schema embedding failed: {str(e)}")
    
    async def process_query(self, query: str) -> Dict[str, Any]:
        """Process natural language query"""
        start_time = time.time()
        
        try:
            if not self.db_connection:
                return {
                    "success": False,
                    "query": query,
                    "error": "No database connected"
                }
            
            # Step 1: Find relevant tables using vector search
            relevant_tables = await self.find_relevant_tables(query)
            
            # Step 2: Generate SQL using Groq directly
            sql_query = await self.generate_sql_with_groq(query)
            
            # Step 3: Execute the SQL query
            result = await self.execute_sql_query(sql_query)
            
            execution_time = time.time() - start_time
            
            # Step 4: Generate natural language response
            nlp_response = await self.generate_natural_language_response(
                query, sql_query, result, execution_time * 1000
            )
            
            return {
                "success": True,
                "query": query,
                "sql_query": sql_query,
                "result": result,
                "nlp_response": nlp_response,
                "relevant_tables": relevant_tables,
                "execution_time": execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Query processing failed: {str(e)}")
            
            return {
                "success": False,
                "query": query,
                "error": str(e),
                "execution_time": execution_time
            }
    
    async def find_relevant_tables(self, query: str) -> List[str]:
        """Find relevant tables using production embedding storage"""
        try:
            if not self.current_database:
                return []
            
            # Search for relevant tables using production storage
            results = self.embedding_storage.search_similar_tables(query, self.current_database, top_k=5)
            
            relevant_tables = []
            for result in results:
                if result.get("similarity", 0) > 0.3:  # Threshold for relevance
                    relevant_tables.append(result["table_name"])
            
            return relevant_tables
            
        except Exception as e:
            logger.error(f"Table search failed: {str(e)}")
            return []
    
    async def generate_sql_with_groq(self, query: str) -> str:
        """Generate SQL query using Groq directly"""
        try:
            # Create schema context
            schema_context = ""
            for table_name, table_info in self.schema_info.items():
                schema_context += f"\nTable: {table_name}\n"
                schema_context += "Columns:\n"
                for col in table_info["columns"]:
                    schema_context += f"  {col[0]} ({col[1]})\n"
            
            # Create prompt for SQL generation
            prompt = f"""
You are a MySQL SQL expert. Convert the following natural language query to a valid MySQL SQL query.

Database Schema:
{schema_context}

Natural Language Query: {query}

IMPORTANT RULES:
1. ONLY generate SELECT statements - no INSERT, UPDATE, DELETE, DROP, etc.
2. Use proper MySQL syntax with correct JOIN statements
3. Always include appropriate WHERE clauses when filtering data
4. Use LIMIT 100 to prevent large result sets
5. Use backticks around table and column names: `table_name`, `column_name`
6. Ensure all JOINs have proper ON conditions
7. Use proper GROUP BY when using aggregate functions like COUNT, SUM, AVG
8. Return ONLY the SQL query - no explanations, no markdown formatting
9. Make sure the query is syntactically correct and complete

Example format:
SELECT `column1`, `column2` 
FROM `table1` 
WHERE `condition` 
LIMIT 100;

SQL Query:
"""
            
            # Call Groq API
            response = self.groq_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            sql_query = response.choices[0].message.content.strip()
            
            # Clean up the SQL query
            if sql_query.startswith("```sql"):
                sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            elif sql_query.startswith("```"):
                sql_query = sql_query.replace("```", "").strip()
            
            # Remove any leading/trailing whitespace and ensure it ends with semicolon
            sql_query = sql_query.strip()
            if not sql_query.endswith(';'):
                sql_query += ';'
            
            # Fix backtick encoding issues - replace malformed backticks
            sql_query = sql_query.replace('`', '`')  # Replace malformed backticks with proper ones
            
            # Basic validation - ensure it's a SELECT statement
            if not sql_query.upper().strip().startswith('SELECT'):
                raise ValueError("Generated query is not a SELECT statement")
            
            # Validate SQL syntax
            if not self._validate_sql_query(sql_query):
                raise ValueError("Generated query has syntax errors")
            
            # Log the generated SQL for debugging
            logger.info(f"Generated SQL: {sql_query}")
            
            return sql_query
            
        except Exception as e:
            logger.error(f"SQL generation failed: {str(e)}")
            raise e
    
    async def execute_sql_query(self, sql_query: str) -> Any:
        """Execute SQL query and return results"""
        try:
            cursor = self.db_connection.cursor()
            
            # Log the SQL query being executed
            logger.info(f"Executing SQL: {sql_query}")
            
            cursor.execute(sql_query)
            
            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Get results
            results = cursor.fetchall()
            
            # Convert to list of dictionaries and serialize non-JSON types
            result_list = []
            for row in results:
                row_dict = dict(zip(columns, row))
                # Serialize non-JSON serializable objects
                serialized_row = self._serialize_row(row_dict)
                result_list.append(serialized_row)
            
            cursor.close()
            logger.info(f"Query executed successfully, returned {len(result_list)} rows")
            return result_list
            
        except Exception as e:
            logger.error(f"SQL execution failed: {str(e)}")
            # Provide more specific error information
            error_msg = str(e)
            if "syntax" in error_msg.lower():
                error_msg = f"SQL Syntax Error: {error_msg}"
            elif "table" in error_msg.lower() and "doesn't exist" in error_msg.lower():
                error_msg = f"Table Not Found: {error_msg}"
            elif "column" in error_msg.lower() and "doesn't exist" in error_msg.lower():
                error_msg = f"Column Not Found: {error_msg}"
            
            raise Exception(error_msg)
    
    def _serialize_row(self, row_dict: Dict) -> Dict:
        """Convert non-JSON serializable objects to serializable types"""
        import decimal
        import datetime
        
        serialized_row = {}
        for key, value in row_dict.items():
            if isinstance(value, decimal.Decimal):
                # Convert Decimal to float
                serialized_row[key] = float(value)
            elif isinstance(value, datetime.datetime):
                # Convert datetime to ISO string
                serialized_row[key] = value.isoformat()
            elif isinstance(value, datetime.date):
                # Convert date to ISO string
                serialized_row[key] = value.isoformat()
            elif isinstance(value, datetime.time):
                # Convert time to string
                serialized_row[key] = str(value)
            else:
                # Keep other types as-is
                serialized_row[key] = value
        
        return serialized_row
    
    async def generate_natural_language_response(self, query: str, sql_query: str, results: list, execution_time: float = None) -> str:
        """Generate a natural language response explaining the query results"""
        try:
            # Count results
            result_count = len(results) if results else 0
            
            # Create response prompt
            prompt = f"""
You are a helpful SQL AI assistant. Generate a concise, conversational response explaining the query results.

User Query: {query}
Generated SQL: {sql_query}
Results: {results if results else []}  # Show ALL results
Total Results: {result_count}
Execution Time: {execution_time}ms (if available)

Guidelines:
1. Be conversational and helpful like ChatGPT
2. Keep responses CONCISE - maximum 2-3 sentences
3. Focus on answering the user's question directly
4. Don't mention technical details (SQL, table names, columns, etc.)
5. Don't explain how the query works
6. Don't offer additional queries unless specifically asked
7. Use a friendly, professional tone
8. Do NOT include random numbers, bullet points, or incomplete sentences

CRITICAL RULE: If the query asks for a LIST of items, you MUST include ALL items from the results in your response. Do not truncate or summarize lists.

Examples:
- For "list customers": "I found {result_count} customers: John Doe, Jane Smith, Bob Johnson, Alice Brown, Charlie Wilson."
- For "show me products": "Here are {result_count} products: Laptop, Mouse, Keyboard."
- For "count orders": "You have {result_count} orders in the system."
- For "customer purchases": "I found {result_count} purchase records from customers."

IMPORTANT: Your response must be complete and accurate. If you say "I found X items", you must list ALL X items.

Response:
"""
            
            # Call Groq API for natural language response
            response = self.groq_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1200  # Increased further to handle complete lists
            )
            
            nlp_response = response.choices[0].message.content.strip()
            logger.info(f"Generated NLP response: {nlp_response}")
            return nlp_response
            
        except Exception as e:
            logger.error(f"NLP response generation failed: {str(e)}")
            # Fallback response - concise and direct
            result_count = len(results) if results else 0
            if result_count > 0:
                return f"I found {result_count} results for your query."
            else:
                return "No results were found for your query."
    
    def _validate_sql_query(self, sql_query: str) -> bool:
        """Basic SQL query validation"""
        try:
            sql_upper = sql_query.upper().strip()
            
            # Check for basic SQL structure
            if not sql_upper.startswith('SELECT'):
                return False
            
            # Check for balanced parentheses
            if sql_query.count('(') != sql_query.count(')'):
                return False
            
            # Check for balanced quotes
            single_quotes = sql_query.count("'")
            double_quotes = sql_query.count('"')
            if single_quotes % 2 != 0 or double_quotes % 2 != 0:
                return False
            
            # Check for basic SELECT structure
            if 'FROM' not in sql_upper:
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_database_schema(self) -> Dict[str, Any]:
        """Get current database schema information"""
        try:
            if not self.db_connection:
                return {"error": "No database connected"}
            
            tables = list(self.schema_info.keys())
            
            return {
                "tables": tables,
                "total_tables": len(tables),
                "schema_info": self.schema_info
            }
            
        except Exception as e:
            logger.error(f"Schema retrieval failed: {str(e)}")
            return {"error": str(e)}
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the SQL Agent"""
        embedding_health = self.embedding_storage.health_check()
        storage_stats = self.embedding_storage.get_storage_stats()
        
        return {
            "status": "healthy" if embedding_health["status"] == "healthy" else "unhealthy",
            "database_connected": self.db_connection is not None,
            "llm_configured": self.groq_client is not None,
            "embedding_storage": embedding_health,
            "storage_stats": storage_stats,
            "model": settings.GROQ_MODEL,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
        }