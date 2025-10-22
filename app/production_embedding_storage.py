# Production Embedding Storage System
import os
import json
import pickle
import numpy as np
from typing import Dict, List, Any, Optional
from sentence_transformers import SentenceTransformer
import logging
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)

class ProductionEmbeddingStorage:
    """
    Production-ready embedding storage system that replaces ChromaDB
    with better performance, scalability, and organization.
    """
    
    def __init__(self, storage_dir: str = "./embeddings_storage"):
        self.storage_dir = storage_dir
        self.embeddings_model = None
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"
        self.model_cache_dir = None
        
        # Create storage structure
        self.create_storage_structure()
        
        # Initialize model
        self.initialize_model()
        
        logger.info(f"Production Embedding Storage initialized at: {self.storage_dir}")
    
    def create_storage_structure(self):
        """Create organized storage directory structure"""
        directories = [
            self.storage_dir,
            f"{self.storage_dir}/models",
            f"{self.storage_dir}/embeddings",
            f"{self.storage_dir}/schemas",
            f"{self.storage_dir}/cache",
            f"{self.storage_dir}/logs"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        # Create index file
        self.index_file = f"{self.storage_dir}/index.json"
        if not os.path.exists(self.index_file):
            self.update_index({})
        
        logger.info(f"Storage structure created at: {self.storage_dir}")
    
    def initialize_model(self):
        """Initialize embedding model with local caching"""
        try:
            # Create model cache directory
            model_name_clean = self.model_name.replace('/', '_')
            self.model_cache_dir = f"{self.storage_dir}/models/{model_name_clean}"
            
            if os.path.exists(self.model_cache_dir):
                logger.info(f"Loading cached model from: {self.model_cache_dir}")
                self.embeddings_model = SentenceTransformer(self.model_cache_dir)
            else:
                logger.info(f"Downloading and caching model: {self.model_name}")
                self.embeddings_model = SentenceTransformer(self.model_name)
                self.embeddings_model.save(self.model_cache_dir)
                logger.info(f"Model cached at: {self.model_cache_dir}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize model: {str(e)}")
            return False
    
    def store_schema_embeddings(self, database_name: str, schema_data: Dict[str, Any]) -> bool:
        """
        Store schema embeddings for a database
        
        Args:
            database_name: Name of the database
            schema_data: Dictionary containing table schemas
            
        Returns:
            bool: Success status
        """
        try:
            if not self.embeddings_model:
                logger.error("Embedding model not initialized")
                return False
            
            # Create database-specific storage
            db_storage_dir = f"{self.storage_dir}/embeddings/{database_name}"
            os.makedirs(db_storage_dir, exist_ok=True)
            
            embeddings_data = {}
            total_tables = len(schema_data)
            
            logger.info(f"Processing {total_tables} tables for database: {database_name}")
            
            for i, (table_name, table_info) in enumerate(schema_data.items()):
                try:
                    # Create embedding text
                    embedding_text = self.create_embedding_text(table_name, table_info)
                    
                    # Generate embedding
                    embedding = self.embeddings_model.encode(embedding_text)
                    
                    # Store embedding data
                    embeddings_data[table_name] = {
                        "text": embedding_text,
                        "embedding": embedding.tolist(),
                        "metadata": {
                            "table_name": table_name,
                            "database_name": database_name,
                            "columns": table_info.get("columns", []),
                            "sample_data": self._serialize_sample_data(table_info.get("sample_data", [])),
                            "created_at": datetime.now().isoformat(),
                            "embedding_dim": len(embedding)
                        }
                    }
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"Processed {i + 1}/{total_tables} tables")
                        
                except Exception as e:
                    logger.error(f"Failed to process table {table_name}: {str(e)}")
                    continue
            
            # Save embeddings to file
            embeddings_file = f"{db_storage_dir}/embeddings.json"
            with open(embeddings_file, 'w', encoding='utf-8') as f:
                json.dump(embeddings_data, f, indent=2, ensure_ascii=False)
            
            # Save schema to schemas directory
            schema_file = f"{self.storage_dir}/schemas/{database_name}_schema.json"
            with open(schema_file, 'w', encoding='utf-8') as f:
                json.dump(schema_data, f, indent=2, ensure_ascii=False)
            
            # Update index
            self.update_database_index(database_name, len(embeddings_data))
            
            logger.info(f"Successfully stored embeddings for {len(embeddings_data)} tables in {database_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store schema embeddings for {database_name}: {str(e)}")
            return False
    
    def _serialize_sample_data(self, sample_data):
        """Serialize sample data to make it JSON serializable"""
        try:
            serialized = []
            for row in sample_data:
                if isinstance(row, (list, tuple)):
                    serialized_row = []
                    for item in row:
                        if hasattr(item, 'isoformat'):  # datetime objects
                            serialized_row.append(item.isoformat())
                        else:
                            serialized_row.append(str(item))
                    serialized.append(serialized_row)
                else:
                    if hasattr(row, 'isoformat'):  # datetime objects
                        serialized.append(row.isoformat())
                    else:
                        serialized.append(str(row))
            return serialized
        except Exception as e:
            logger.error(f"Failed to serialize sample data: {str(e)}")
            return []
    
    def create_embedding_text(self, table_name: str, table_info: Dict[str, Any]) -> str:
        """Create optimized text for embedding generation"""
        text_parts = [f"Table: {table_name}"]
        
        # Add column information
        if "columns" in table_info and table_info["columns"]:
            text_parts.append("Columns:")
            for col in table_info["columns"]:
                if isinstance(col, (list, tuple)) and len(col) >= 2:
                    col_name = col[0]
                    col_type = col[1]
                    col_desc = col[2] if len(col) > 2 else ""
                    text_parts.append(f"  {col_name} ({col_type}) {col_desc}")
                else:
                    text_parts.append(f"  {col}")
        
        # Add sample data context (limit to avoid token issues)
        if "sample_data" in table_info and table_info["sample_data"]:
            text_parts.append("Sample data:")
            for row in table_info["sample_data"][:3]:  # Limit to 3 rows
                if isinstance(row, (list, tuple)):
                    text_parts.append(f"  {', '.join(map(str, row))}")
                else:
                    text_parts.append(f"  {row}")
        
        return "\n".join(text_parts)
    
    def search_similar_tables(self, query: str, database_name: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar tables using embeddings
        
        Args:
            query: Natural language query
            database_name: Name of the database to search
            top_k: Number of top results to return
            
        Returns:
            List of similar tables with metadata
        """
        try:
            if not self.embeddings_model:
                logger.error("Embedding model not initialized")
                return []
            
            # Load embeddings for database
            embeddings_file = f"{self.storage_dir}/embeddings/{database_name}/embeddings.json"
            
            if not os.path.exists(embeddings_file):
                logger.warning(f"No embeddings found for database: {database_name}")
                return []
            
            with open(embeddings_file, 'r', encoding='utf-8') as f:
                embeddings_data = json.load(f)
            
            if not embeddings_data:
                logger.warning(f"No embeddings data in {database_name}")
                return []
            
            # Generate query embedding
            query_embedding = self.embeddings_model.encode(query)
            
            # Calculate similarities
            similarities = []
            for table_name, data in embeddings_data.items():
                try:
                    table_embedding = np.array(data["embedding"])
                    similarity = np.dot(query_embedding, table_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(table_embedding)
                    )
                    
                    similarities.append({
                        "table_name": table_name,
                        "similarity": float(similarity),
                        "metadata": data["metadata"],
                        "text": data["text"]
                    })
                except Exception as e:
                    logger.error(f"Failed to calculate similarity for {table_name}: {str(e)}")
                    continue
            
            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Failed to search similar tables: {str(e)}")
            return []
    
    def get_database_schemas(self) -> Dict[str, Any]:
        """Get all stored database schemas"""
        schemas = {}
        schemas_dir = f"{self.storage_dir}/schemas"
        
        if os.path.exists(schemas_dir):
            for filename in os.listdir(schemas_dir):
                if filename.endswith("_schema.json"):
                    database_name = filename.replace("_schema.json", "")
                    try:
                        with open(f"{schemas_dir}/{filename}", 'r', encoding='utf-8') as f:
                            schemas[database_name] = json.load(f)
                    except Exception as e:
                        logger.error(f"Failed to load schema for {database_name}: {str(e)}")
        
        return schemas
    
    def update_database_index(self, database_name: str, table_count: int):
        """Update the database index"""
        try:
            index_data = self.get_index()
            index_data[database_name] = {
                "table_count": table_count,
                "last_updated": datetime.now().isoformat(),
                "embeddings_file": f"{self.storage_dir}/embeddings/{database_name}/embeddings.json",
                "schema_file": f"{self.storage_dir}/schemas/{database_name}_schema.json"
            }
            self.update_index(index_data)
        except Exception as e:
            logger.error(f"Failed to update index for {database_name}: {str(e)}")
    
    def get_index(self) -> Dict[str, Any]:
        """Get the current index"""
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def update_index(self, index_data: Dict[str, Any]):
        """Update the index file"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to update index: {str(e)}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get comprehensive storage statistics"""
        stats = {
            "total_databases": 0,
            "total_tables": 0,
            "total_embeddings": 0,
            "storage_size_mb": 0,
            "model_cache_size_mb": 0,
            "databases": {}
        }
        
        try:
            # Get index data
            index_data = self.get_index()
            stats["total_databases"] = len(index_data)
            
            # Calculate stats for each database
            for db_name, db_info in index_data.items():
                stats["databases"][db_name] = {
                    "table_count": db_info.get("table_count", 0),
                    "last_updated": db_info.get("last_updated", "Unknown")
                }
                stats["total_tables"] += db_info.get("table_count", 0)
                
                # Count actual embeddings
                embeddings_file = db_info.get("embeddings_file")
                if embeddings_file and os.path.exists(embeddings_file):
                    with open(embeddings_file, 'r', encoding='utf-8') as f:
                        embeddings_data = json.load(f)
                    stats["total_embeddings"] += len(embeddings_data)
            
            # Calculate storage size
            total_size = 0
            for root, dirs, files in os.walk(self.storage_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
            
            stats["storage_size_mb"] = round(total_size / (1024 * 1024), 2)
            
            # Calculate model cache size
            if self.model_cache_dir and os.path.exists(self.model_cache_dir):
                model_size = 0
                for root, dirs, files in os.walk(self.model_cache_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        model_size += os.path.getsize(file_path)
                stats["model_cache_size_mb"] = round(model_size / (1024 * 1024), 2)
            
        except Exception as e:
            logger.error(f"Failed to calculate storage stats: {str(e)}")
        
        return stats
    
    def cleanup_old_embeddings(self, days_old: int = 30):
        """Clean up old embeddings to save space"""
        try:
            cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            cleaned_count = 0
            
            for root, dirs, files in os.walk(f"{self.storage_dir}/embeddings"):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        if os.path.getmtime(file_path) < cutoff_date:
                            os.remove(file_path)
                            cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old embedding files")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old embeddings: {str(e)}")
            return 0
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the storage system"""
        health = {
            "status": "healthy",
            "model_loaded": False,
            "storage_accessible": False,
            "index_valid": False,
            "issues": []
        }
        
        try:
            # Check model
            if self.embeddings_model:
                health["model_loaded"] = True
            else:
                health["issues"].append("Embedding model not loaded")
            
            # Check storage
            if os.path.exists(self.storage_dir):
                health["storage_accessible"] = True
            else:
                health["issues"].append("Storage directory not accessible")
            
            # Check index
            try:
                self.get_index()
                health["index_valid"] = True
            except:
                health["issues"].append("Index file corrupted")
            
            # Overall status
            if health["issues"]:
                health["status"] = "unhealthy"
            
        except Exception as e:
            health["status"] = "error"
            health["issues"].append(f"Health check failed: {str(e)}")
        
        return health

# Example usage and testing
if __name__ == "__main__":
    # Initialize storage
    storage = ProductionEmbeddingStorage()
    
    # Health check
    health = storage.health_check()
    print("Health Check:", health)
    
    # Get stats
    stats = storage.get_storage_stats()
    print("Storage Stats:", stats)
