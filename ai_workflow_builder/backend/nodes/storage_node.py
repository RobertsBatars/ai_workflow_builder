"""
Storage node implementation for both static and vector storage.
"""
import json
import os
import sqlite3
from typing import Dict, Any, List, Union, Optional

import numpy as np
import faiss

from .base import BaseNode, NodeRegistry
from ...shared.models import StorageNodeConfig


class StorageNode(BaseNode):
    """
    Node for storing and retrieving data.
    Supports both static (key-value) and vector storage.
    """
    def __init__(self, config: StorageNodeConfig):
        super().__init__(config)
        self.storage_type = config.parameters.get("storage_type", "static")
        self.dimension = config.parameters.get("dimension", 768)
        self.persist = config.parameters.get("persist", False)
        
        # Initialize the storage based on type
        self._initialize_storage()
        
        # Setup ports based on storage type
        self._setup_ports_by_type()
    
    def _initialize_storage(self):
        """Initialize the appropriate storage type."""
        if self.storage_type == "static":
            self.storage = {}  # Simple dict for static storage
        elif self.storage_type == "vector":
            self.storage = VectorStorage(dimension=self.dimension)
        else:
            raise ValueError(f"Unknown storage type: {self.storage_type}")
    
    def _setup_ports_by_type(self):
        """Set up input and output ports based on storage type."""
        if self.storage_type == "static":
            self.inputs = {
                "key": None,
                "value": None,
                "operation": "set"  # set, get, delete
            }
            self.outputs = {
                "result": None,
                "success": None,
                "error": None
            }
        elif self.storage_type == "vector":
            self.inputs = {
                "text": None,
                "embedding": None,
                "query_embedding": None,
                "top_k": 3,
                "operation": "add"  # add, search, delete
            }
            self.outputs = {
                "results": None,
                "success": None,
                "error": None
            }
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the storage node operation."""
        try:
            if self.storage_type == "static":
                return await self._execute_static_storage()
            elif self.storage_type == "vector":
                return await self._execute_vector_storage()
            else:
                error_msg = f"Unknown storage type: {self.storage_type}"
                self.outputs["error"] = error_msg
                return {"error": error_msg}
                
        except Exception as e:
            error_msg = f"Storage node execution error: {str(e)}"
            if "error" in self.outputs:
                self.outputs["error"] = error_msg
            return {"error": error_msg}
    
    async def _execute_static_storage(self) -> Dict[str, Any]:
        """Execute operations for static storage."""
        key = self.inputs.get("key")
        value = self.inputs.get("value")
        operation = self.inputs.get("operation", "set")
        
        if operation == "set":
            if key is None:
                raise ValueError("Key is required for 'set' operation")
            self.storage[key] = value
            self.outputs["result"] = value
            self.outputs["success"] = True
        
        elif operation == "get":
            if key is None:
                raise ValueError("Key is required for 'get' operation")
            if key in self.storage:
                self.outputs["result"] = self.storage[key]
                self.outputs["success"] = True
            else:
                self.outputs["result"] = None
                self.outputs["success"] = False
                self.outputs["error"] = f"Key '{key}' not found"
        
        elif operation == "delete":
            if key is None:
                raise ValueError("Key is required for 'delete' operation")
            if key in self.storage:
                del self.storage[key]
                self.outputs["success"] = True
            else:
                self.outputs["success"] = False
                self.outputs["error"] = f"Key '{key}' not found"
        
        elif operation == "list":
            self.outputs["result"] = list(self.storage.keys())
            self.outputs["success"] = True
        
        else:
            raise ValueError(f"Unknown operation '{operation}' for static storage")
        
        return self.outputs
    
    async def _execute_vector_storage(self) -> Dict[str, Any]:
        """Execute operations for vector storage."""
        text = self.inputs.get("text")
        embedding = self.inputs.get("embedding")
        query_embedding = self.inputs.get("query_embedding")
        top_k = self.inputs.get("top_k", 3)
        index_id = self.inputs.get("index_id")
        operation = self.inputs.get("operation", "add")
        
        if operation == "add":
            if embedding is None:
                raise ValueError("Embedding is required for 'add' operation")
            
            # Add the embedding and text to storage
            idx = self.storage.add_embedding(embedding, text)
            self.outputs["results"] = {"id": idx}
            self.outputs["success"] = True
        
        elif operation == "search":
            if query_embedding is None:
                raise ValueError("Query embedding is required for 'search' operation")
            
            # Search for similar vectors
            results = self.storage.search(query_embedding, k=top_k)
            self.outputs["results"] = results
            self.outputs["success"] = True
        
        elif operation == "delete":
            if index_id is None:
                # Try to delete by embedding if no index_id provided
                if embedding is None:
                    raise ValueError("Either index_id or embedding is required for 'delete' operation")
                    
                # Find the closest embedding and delete it
                success = self.storage.delete_by_embedding(embedding)
                self.outputs["success"] = success
                if not success:
                    self.outputs["error"] = "Could not find matching embedding to delete"
            else:
                # Delete by index ID
                success = self.storage.delete_by_id(index_id)
                self.outputs["success"] = success
                if not success:
                    self.outputs["error"] = f"Could not delete embedding with ID {index_id}"
        
        elif operation == "clear":
            # Clear all vectors from storage
            self.storage.clear()
            self.outputs["success"] = True
        
        elif operation == "count":
            # Return the number of vectors in storage
            count = self.storage.count()
            self.outputs["results"] = {"count": count}
            self.outputs["success"] = True
        
        else:
            raise ValueError(f"Unknown operation '{operation}' for vector storage")
        
        # Persist after modification operations
        if self.persist and operation in ["add", "delete", "clear"]:
            # Generate a persist path if not set
            if not hasattr(self.storage, "persist_path") or not self.storage.persist_path:
                import tempfile
                import os
                persist_dir = os.path.join(tempfile.gettempdir(), "ai_workflow_builder", "vector_store")
                os.makedirs(persist_dir, exist_ok=True)
                self.storage.persist_path = os.path.join(persist_dir, f"storage_{self.id}")
            
            # Save the storage
            self.storage.save(self.storage.persist_path)
        
        return self.outputs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the node to a dictionary, including storage data for persistence."""
        node_dict = super().to_dict()
        
        # Only include storage data if persistence is enabled
        if self.persist:
            if self.storage_type == "static":
                node_dict["state"]["storage_data"] = self.storage
            elif self.storage_type == "vector":
                # For vector storage, serialization requires special handling
                # that would be implemented in the VectorStorage class
                if hasattr(self.storage, "to_dict"):
                    node_dict["state"]["storage_data"] = self.storage.to_dict()
        
        return node_dict
    
    def from_dict(self, data: Dict[str, Any]):
        """Restore node state from a dictionary, including storage data."""
        super().from_dict(data)
        
        # Restore storage data if available
        if "state" in data and "storage_data" in data["state"]:
            if self.storage_type == "static":
                self.storage = data["state"]["storage_data"]
            elif self.storage_type == "vector":
                # For vector storage, deserialization requires special handling
                if hasattr(self.storage, "from_dict"):
                    self.storage.from_dict(data["state"]["storage_data"])


class VectorStorage:
    """Vector storage implementation using FAISS."""
    def __init__(self, dimension: int = 768, persist_path: Optional[str] = None):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.texts = []  # Store the associated texts
        self.persist_path = persist_path
        self.deleted_indices = set()  # Track deleted indices
        
        # SQLite connection for metadata (optional)
        self.sqlite_conn = None
        
        # Load data if persist path is provided
        if persist_path and os.path.exists(f"{persist_path}.index"):
            self.load(persist_path)
    
    def add_embedding(self, embedding: List[float], text: Optional[str] = None) -> int:
        """
        Add an embedding to the vector store.
        
        Args:
            embedding: Vector embedding to add
            text: Optional text associated with the embedding
            
        Returns:
            The index ID of the added embedding
        """
        # Convert to numpy array if it's a list
        if isinstance(embedding, list):
            embedding = np.array([embedding], dtype=np.float32)
        elif isinstance(embedding, np.ndarray) and embedding.ndim == 1:
            # Ensure it's a 2D array with shape (1, dimension)
            embedding = embedding.reshape(1, -1).astype(np.float32)
        
        # Add to the FAISS index
        self.index.add(embedding)
        
        # Store the associated text
        self.texts.append(text if text is not None else "")
        
        # Get the index of the added embedding
        idx = len(self.texts) - 1
        
        # Persist if a path is set
        if self.persist_path:
            self.save(self.persist_path)
            
        return idx
    
    def search(self, query: List[float], k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for the k nearest vectors to the query.
        
        Args:
            query: Vector embedding to search for
            k: Number of results to return
            
        Returns:
            List of dictionaries with id, text, and distance
        """
        # Convert to numpy array if it's a list
        if isinstance(query, list):
            query = np.array([query], dtype=np.float32)
        elif isinstance(query, np.ndarray) and query.ndim == 1:
            # Ensure it's a 2D array with shape (1, dimension)
            query = query.reshape(1, -1).astype(np.float32)
        
        # Handle case when the index is empty
        if self.index.ntotal == 0:
            return []
        
        # We may need to get more results if there are deleted indices
        actual_k = k
        if self.deleted_indices:
            actual_k = min(k + len(self.deleted_indices), self.index.ntotal)
        
        # Search the FAISS index
        distances, indices = self.index.search(query, actual_k)
        
        # Format the results, filtering out deleted indices
        results = []
        for i, idx in enumerate(indices[0]):
            # Skip deleted indices
            if idx in self.deleted_indices:
                continue
                
            if idx < len(self.texts):  # Ensure index is valid
                results.append({
                    "id": int(idx),
                    "text": self.texts[idx],
                    "distance": float(distances[0][i])
                })
                
            # Stop once we have k results
            if len(results) >= k:
                break
        
        return results
    
    def delete_by_id(self, index_id: int) -> bool:
        """
        Delete an embedding by its index ID.
        
        Args:
            index_id: The index to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        if index_id < 0 or index_id >= len(self.texts):
            return False
        
        # Mark as deleted
        self.deleted_indices.add(index_id)
        
        # Replace the text with a deleted marker
        self.texts[index_id] = "__DELETED__"
        
        # Persist if a path is set
        if self.persist_path:
            self.save(self.persist_path)
            
        return True
    
    def delete_by_embedding(self, embedding: List[float]) -> bool:
        """
        Delete the embedding closest to the provided embedding.
        
        Args:
            embedding: Vector embedding to match for deletion
            
        Returns:
            True if deleted successfully, False otherwise
        """
        # Convert to numpy array if it's a list
        if isinstance(embedding, list):
            embedding = np.array([embedding], dtype=np.float32)
        elif isinstance(embedding, np.ndarray) and embedding.ndim == 1:
            # Ensure it's a 2D array with shape (1, dimension)
            embedding = embedding.reshape(1, -1).astype(np.float32)
        
        # Handle case when the index is empty
        if self.index.ntotal == 0:
            return False
        
        # Find the closest embedding
        distances, indices = self.index.search(embedding, 1)
        
        # Get the index
        idx = indices[0][0]
        
        # Delete by ID
        return self.delete_by_id(idx)
    
    def clear(self):
        """Clear all vectors from storage."""
        # Reset the FAISS index
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # Clear texts and deleted indices
        self.texts = []
        self.deleted_indices = set()
        
        # Persist if a path is set
        if self.persist_path:
            self.save(self.persist_path)
    
    def count(self) -> int:
        """Get the number of active vectors in storage."""
        return self.index.ntotal - len(self.deleted_indices)
    
    def save(self, path: str):
        """
        Save the vector store to disk.
        
        Args:
            path: Base path for saving the index and metadata
        """
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Save the FAISS index
        faiss.write_index(self.index, f"{path}.index")
        
        # Save the texts and deleted indices
        metadata = {
            "texts": self.texts,
            "deleted_indices": list(self.deleted_indices),
            "dimension": self.dimension,
            "count": self.index.ntotal
        }
        
        with open(f"{path}.metadata.json", "w") as f:
            json.dump(metadata, f)
    
    def load(self, path: str):
        """
        Load the vector store from disk.
        
        Args:
            path: Base path for loading the index and metadata
        """
        # Load the FAISS index if it exists
        if os.path.exists(f"{path}.index"):
            self.index = faiss.read_index(f"{path}.index")
        
        # Load the metadata if it exists
        if os.path.exists(f"{path}.metadata.json"):
            with open(f"{path}.metadata.json", "r") as f:
                metadata = json.load(f)
                self.texts = metadata.get("texts", [])
                self.deleted_indices = set(metadata.get("deleted_indices", []))
                self.dimension = metadata.get("dimension", self.dimension)
        # Backward compatibility for older format
        elif os.path.exists(f"{path}.texts.json"):
            with open(f"{path}.texts.json", "r") as f:
                self.texts = json.load(f)
    
    def _initialize_sqlite(self, path: str):
        """Initialize SQLite database for additional metadata."""
        self.sqlite_conn = sqlite3.connect(f"{path}.sqlite")
        cursor = self.sqlite_conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id INTEGER PRIMARY KEY,
            text TEXT,
            metadata TEXT,
            deleted INTEGER DEFAULT 0
        )
        """)
        
        self.sqlite_conn.commit()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the vector store to a dictionary for serialization."""
        return {
            "dimension": self.dimension,
            "count": self.index.ntotal,
            "active_count": self.count(),
            "texts": self.texts,
            "deleted_indices": list(self.deleted_indices),
            "persist_path": self.persist_path
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """Restore the vector store from a dictionary."""
        self.dimension = data.get("dimension", 768)
        self.texts = data.get("texts", [])
        self.deleted_indices = set(data.get("deleted_indices", []))
        self.persist_path = data.get("persist_path", self.persist_path)
        
        # The FAISS index would typically be loaded separately
        # This just updates metadata


# Register this node type with the registry
NodeRegistry.register("storage", StorageNode)