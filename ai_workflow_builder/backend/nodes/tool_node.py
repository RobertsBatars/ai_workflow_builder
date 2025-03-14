"""
Tool node implementation for using prebuilt or custom tools.
"""
import json
import importlib
import asyncio
from typing import Dict, Any, List, Optional, Callable

from .base import BaseNode, NodeRegistry
from ...shared.models import ToolNodeConfig


class ToolNode(BaseNode):
    """
    Node for executing prebuilt or custom tools.
    """
    def __init__(self, config: ToolNodeConfig):
        super().__init__(config)
        self.tool_name = config.parameters.get("tool_name", "")
        self.tool_parameters = config.parameters.get("tool_parameters", {})
        
        # Initialize the tool
        self.tool = None
        self._load_tool()
        
        # Setup standard ports
        self.inputs = {
            "input": None,
            "parameters": self.tool_parameters
        }
        
        self.outputs = {
            "output": None,
            "error": None
        }
    
    def _load_tool(self):
        """Load the specified tool from the tool registry."""
        if not self.tool_name:
            return
        
        try:
            self.tool = ToolRegistry.get_tool(self.tool_name)
        except Exception as e:
            # Log error but don't raise so the node can be initialized
            print(f"Error loading tool '{self.tool_name}': {str(e)}")
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the tool with the provided inputs."""
        input_data = self.inputs.get("input")
        parameters = self.inputs.get("parameters") or self.tool_parameters
        
        if not self.tool_name:
            error_msg = "No tool specified for Tool node"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
        
        if not self.tool:
            try:
                self._load_tool()
            except Exception as e:
                error_msg = f"Failed to load tool '{self.tool_name}': {str(e)}"
                self.outputs["error"] = error_msg
                return {"error": error_msg}
            
            if not self.tool:
                error_msg = f"Tool '{self.tool_name}' not found"
                self.outputs["error"] = error_msg
                return {"error": error_msg}
        
        try:
            # Execute the tool with the input and parameters
            result = await self.tool.execute(input_data, parameters)
            
            if isinstance(result, dict) and "error" in result and result["error"]:
                self.outputs["error"] = result["error"]
                return {"error": result["error"]}
            
            self.outputs["output"] = result
            return self.outputs
            
        except Exception as e:
            error_msg = f"Tool node execution error: {str(e)}"
            self.outputs["error"] = error_msg
            return {"error": error_msg}


class BaseTool:
    """
    Base class for all tools.
    Tools are like plugins that can be used by nodes.
    """
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    async def execute(self, input_data: Any, parameters: Dict[str, Any]) -> Any:
        """
        Execute the tool with the provided input and parameters.
        Must be implemented by derived classes.
        """
        raise NotImplementedError("Tool execution not implemented")
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for the tool's parameters.
        Used for validating tool parameter inputs.
        """
        return {}


class ToolRegistry:
    """
    Registry for tools and factory for creating tool instances.
    """
    _registry = {}
    
    @classmethod
    def register(cls, tool_name: str, tool_class) -> None:
        """Register a tool class for a specific tool name."""
        cls._registry[tool_name] = tool_class
    
    @classmethod
    def get_tool(cls, tool_name: str) -> BaseTool:
        """Get an instance of a tool by name."""
        if tool_name not in cls._registry:
            raise ValueError(f"Tool '{tool_name}' is not registered")
        
        tool_class = cls._registry[tool_name]
        return tool_class()
    
    @classmethod
    def get_tool_names(cls) -> List[str]:
        """Get a list of all registered tool names."""
        return list(cls._registry.keys())
    
    @classmethod
    def register_from_code(cls, tool_name: str, tool_code: str) -> None:
        """Register a tool from Python code."""
        try:
            # Create a new module for the tool
            module_name = f"custom_tool_{tool_name}"
            spec = importlib.util.spec_from_loader(module_name, loader=None)
            module = importlib.util.module_from_spec(spec)
            
            # Execute the tool code in the module context
            exec(tool_code, module.__dict__)
            
            # Check if the tool class is defined
            if not hasattr(module, "Tool"):
                raise ValueError(f"Tool code does not define a 'Tool' class")
            
            # Register the tool
            cls.register(tool_name, module.Tool)
            
        except Exception as e:
            raise ValueError(f"Failed to register tool from code: {str(e)}")


# Register this node type with the registry
NodeRegistry.register("tool", ToolNode)


# Define some built-in tools

class WebSearchTool(BaseTool):
    """
    Tool for performing web searches.
    This is a placeholder implementation.
    """
    def __init__(self):
        super().__init__("web_search", "Search the web for information")
    
    async def execute(self, input_data: Any, parameters: Dict[str, Any]) -> Any:
        """Execute a web search."""
        query = input_data
        if isinstance(input_data, dict) and "query" in input_data:
            query = input_data["query"]
        
        # This is a placeholder for actual web search functionality
        # In a real implementation, this would use a search API
        return {
            "results": [
                {"title": f"Result 1 for '{query}'", "snippet": "This is a placeholder result"},
                {"title": f"Result 2 for '{query}'", "snippet": "This is another placeholder result"}
            ]
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the schema for the tool parameters."""
        return {
            "type": "object",
            "properties": {
                "num_results": {
                    "type": "integer",
                    "description": "Number of search results to return",
                    "default": 5
                },
                "search_engine": {
                    "type": "string",
                    "description": "Search engine to use",
                    "enum": ["google", "bing", "duckduckgo"],
                    "default": "google"
                }
            }
        }


class FileIOTool(BaseTool):
    """
    Tool for reading and writing files.
    This is a placeholder implementation.
    """
    def __init__(self):
        super().__init__("file_io", "Read and write files")
    
    async def execute(self, input_data: Any, parameters: Dict[str, Any]) -> Any:
        """Execute file I/O operations."""
        operation = parameters.get("operation", "read")
        
        if operation == "read":
            file_path = parameters.get("file_path")
            if not file_path:
                return {"error": "No file path provided for read operation"}
            
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                return {"content": content}
            except Exception as e:
                return {"error": f"Error reading file: {str(e)}"}
        
        elif operation == "write":
            file_path = parameters.get("file_path")
            content = parameters.get("content", "")
            
            if not file_path:
                return {"error": "No file path provided for write operation"}
            
            try:
                with open(file_path, "w") as f:
                    f.write(content)
                return {"success": True}
            except Exception as e:
                return {"error": f"Error writing file: {str(e)}"}
        
        else:
            return {"error": f"Unknown operation '{operation}'"}
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the schema for the tool parameters."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "File operation to perform",
                    "enum": ["read", "write"],
                    "default": "read"
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to the file"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file (for write operation)"
                }
            },
            "required": ["file_path"]
        }


# Register built-in tools
ToolRegistry.register("web_search", WebSearchTool)
ToolRegistry.register("file_io", FileIOTool)