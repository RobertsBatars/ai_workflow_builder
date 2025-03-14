"""
Data models and schemas used throughout the application.
These Pydantic models define the structure for nodes, connections, and workflows.
"""
from typing import Dict, List, Tuple, Any, Optional, Union
from pydantic import BaseModel, Field


class Position(BaseModel):
    """Position of a node in the canvas."""
    x: int
    y: int


class Connection(BaseModel):
    """Connection between two nodes."""
    source_node: str
    source_port: str
    target_node: str
    target_port: str


class ToolConfig(BaseModel):
    """Configuration for a tool that can be used by nodes."""
    name: str
    description: str = ""
    api_url: Optional[str] = None
    code: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)


class NodeConfig(BaseModel):
    """Base configuration for all node types."""
    id: str
    type: str
    name: str = ""
    description: str = ""
    position: Position
    parameters: Dict[str, Any] = Field(default_factory=dict)
    input_ports: List[str] = Field(default_factory=list)
    output_ports: List[str] = Field(default_factory=list)


class LLMNodeConfig(NodeConfig):
    """Configuration specific to LLM nodes."""
    type: str = "llm"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "model": "",
            "system_prompt": "",
            "temperature": 0.7,
            "tools": []
        }
    )


class DecisionNodeConfig(NodeConfig):
    """Configuration specific to decision nodes."""
    type: str = "decision"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "condition": "",
            "true_port": "true",
            "false_port": "false"
        }
    )


class CompositeNodeConfig(NodeConfig):
    """Configuration specific to composite nodes."""
    type: str = "composite"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "workflow_json": {}
        }
    )


class StorageNodeConfig(NodeConfig):
    """Configuration specific to storage nodes."""
    type: str = "storage"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "storage_type": "static",  # or "vector"
            "dimension": 768,  # For vector storage
            "persist": False
        }
    )


class CustomPythonNodeConfig(NodeConfig):
    """Configuration specific to custom Python nodes."""
    type: str = "python"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "code": "",
            "requirements": []
        }
    )


class ToolNodeConfig(NodeConfig):
    """Configuration specific to tool nodes."""
    type: str = "tool"
    parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "tool_name": "",
            "tool_parameters": {}
        }
    )


class VirtualizationConfig(BaseModel):
    """Configuration for virtualization settings."""
    type: str = "none"  # none, lightweight, ubuntu
    resource_limits: Dict[str, Any] = Field(default_factory=dict)
    network_access: bool = False


class WorkflowConfig(BaseModel):
    """Complete workflow configuration."""
    name: str = "Untitled Workflow"
    description: str = ""
    nodes: List[NodeConfig] = Field(default_factory=list)
    connections: List[Connection] = Field(default_factory=list)
    tools: List[ToolConfig] = Field(default_factory=list)
    environment: VirtualizationConfig = Field(default_factory=VirtualizationConfig)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StateCheckpoint(BaseModel):
    """Checkpoint for workflow state recovery."""
    workflow: WorkflowConfig
    timestamp: float
    node_states: Dict[str, Any] = Field(default_factory=dict)