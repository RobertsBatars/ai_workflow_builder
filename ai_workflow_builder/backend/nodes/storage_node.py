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
        operation = self.inputs.get("operation", "add")
        
        if operation == "add":
            if embedding is None:
                raise ValueError("Embedding is required for 'add' operation")
            
            # Add the embedding and text to storage
            self.storage.add_embedding(embedding, text)
            self.outputs["success"] = True
        
        elif operation == "search":
            if query_embedding is None:
                raise ValueError("Query embedding is required for 'search' operation")
            
            # Search for similar vectors
            results = self.storage.search(query_embedding, k=top_k)
            self.outputs["results"] = results
            self.outputs["success"] = True
        
        elif operation == "delete":
            if embedding is None:
                raise ValueError("Embedding is required for 'delete' operation")
            
            # Delete is more complex for vector storage and might need implementation
            # based on the specific vector database being used
            # Here we'll just set success to False
            self.outputs["success"] = False
            self.outputs["error"] = "Delete operation not implemented for vector storage"
        
        else:
            raise ValueError(f"Unknown operation '{operation}' for vector storage")
        
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
        
        # Load data if persist path is provided
        if persist_path and os.path.exists(persist_path):
            self.load(persist_path)
    
    def add_embedding(self, embedding: List[float], text: Optional[str] = None):
        """Add an embedding to the vector store."""
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
        
        # Persist if a path is set
        if self.persist_path:
            self.save(self.persist_path)
    
    def search(self, query: List[float], k: int = 3) -> List[Dict[str, Any]]:
        """Search for the k nearest vectors to the query."""
        # Convert to numpy array if it's a list
        if isinstance(query, list):
            query = np.array([query], dtype=np.float32)
        elif isinstance(query, np.ndarray) and query.ndim == 1:
            # Ensure it's a 2D array with shape (1, dimension)
            query = query.reshape(1, -1).astype(np.float32)
        
        # Handle case when the index is empty
        if self.index.ntotal == 0:
            return []
        
        # Search the FAISS index
        distances, indices = self.index.search(query, min(k, self.index.ntotal))
        
        # Format the results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.texts):  # Ensure index is valid
                results.append({
                    "id": int(idx),
                    "text": self.texts[idx],
                    "distance": float(distances[0][i])
                })
        
        return results
    
    def save(self, path: str):
        """Save the vector store to disk."""
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Save the FAISS index
        faiss.write_index(self.index, f"{path}.index")
        
        # Save the texts
        with open(f"{path}.texts.json", "w") as f:
            json.dump(self.texts, f)
    
    def load(self, path: str):
        """Load the vector store from disk."""
        if os.path.exists(f"{path}.index"):
            self.index = faiss.read_index(f"{path}.index")
        
        if os.path.exists(f"{path}.texts.json"):
            with open(f"{path}.texts.json", "r") as f:
                self.texts = json.load(f)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the vector store to a dictionary for serialization."""
        # This would be a simplified representation
        return {
            "dimension": self.dimension,
            "count": self.index.ntotal,
            "texts": self.texts
            # Note: The actual FAISS index would be saved separately
        }
    
    def from_dict(self, data: Dict[str, Any]):
        """Restore the vector store from a dictionary."""
        # This would be a simplified implementation
        self.dimension = data.get("dimension", 768)
        self.texts = data.get("texts", [])
        # Note: The actual FAISS index would be loaded separately


# Register this node type with the registry
NodeRegistry.register("storage", StorageNode)