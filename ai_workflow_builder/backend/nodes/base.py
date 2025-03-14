"""
Base classes for all node types in the workflow system.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Set

from ...shared.models import NodeConfig


class BaseNode(ABC):
    """
    Abstract base class for all node types in the workflow system.
    """
    def __init__(self, config: NodeConfig):
        self.id = config.id
        self.type = config.type
        self.name = config.name or f"{self.type.capitalize()} Node"
        self.description = config.description
        self.config = config
        self.inputs = {}
        self.outputs = {}
        self.state = {}
        self._setup_ports()
        
    def _setup_ports(self):
        """Set up input and output ports based on the node configuration."""
        # Default implementation uses the input_ports and output_ports from config
        for port in self.config.input_ports:
            self.inputs[port] = None
        
        for port in self.config.output_ports:
            self.outputs[port] = None
            
    def set_input(self, port: str, value: Any) -> None:
        """Set the value for an input port."""
        if port in self.inputs:
            self.inputs[port] = value
        else:
            raise ValueError(f"Input port '{port}' not found in node '{self.id}'")
            
    def get_output(self, port: str) -> Any:
        """Get the value from an output port."""
        if port in self.outputs:
            return self.outputs[port]
        raise ValueError(f"Output port '{port}' not found in node '{self.id}'")
    
    @property
    def input_ports(self) -> List[str]:
        """Get list of input port names."""
        return list(self.inputs.keys())
    
    @property
    def output_ports(self) -> List[str]:
        """Get list of output port names."""
        return list(self.outputs.keys())
    
    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """
        Execute the node's function and return the outputs.
        Must be implemented by all derived classes.
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the node to a dictionary representation."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "position": self.config.position.dict(),
            "parameters": self.config.parameters,
            "input_ports": self.input_ports,
            "output_ports": self.output_ports,
            "state": self.state
        }
    
    def reset(self) -> None:
        """Reset the node state."""
        self.state = {}
        for port in self.inputs:
            self.inputs[port] = None
        for port in self.outputs:
            self.outputs[port] = None
            
    def validate_connections(self) -> List[str]:
        """
        Validate that all required inputs are connected.
        Returns a list of error messages, empty if valid.
        """
        errors = []
        for port in self.input_ports:
            if self.inputs[port] is None:
                errors.append(f"Input port '{port}' of node '{self.id}' is not connected")
        return errors


class NodeRegistry:
    """
    Registry for node types and factory for creating nodes from configurations.
    """
    _registry = {}
    
    @classmethod
    def register(cls, node_type: str, node_class):
        """Register a node class for a specific node type."""
        cls._registry[node_type] = node_class
        
    @classmethod
    def create(cls, config: NodeConfig) -> BaseNode:
        """Create a node instance from a configuration."""
        if config.type not in cls._registry:
            raise ValueError(f"Node type '{config.type}' is not registered")
        return cls._registry[config.type](config)
    
    @classmethod
    def get_node_types(cls) -> List[str]:
        """Get a list of all registered node types."""
        return list(cls._registry.keys())