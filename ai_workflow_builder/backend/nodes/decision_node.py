"""
Decision node implementation for branching workflow based on conditions.
"""
from typing import Dict, Any, List

from .base import BaseNode, NodeRegistry
from ...shared.models import DecisionNodeConfig


class DecisionNode(BaseNode):
    """
    Node for creating conditional branches in a workflow.
    Uses Python expressions to evaluate conditions.
    """
    def __init__(self, config: DecisionNodeConfig):
        super().__init__(config)
        self.condition = config.parameters.get("condition", "")
        self.true_port = config.parameters.get("true_port", "true")
        self.false_port = config.parameters.get("false_port", "false")
        
        # Setup standard ports
        self.inputs = {
            "value": None,
            "condition": self.condition
        }
        
        self.outputs = {
            self.true_port: None,
            self.false_port: None,
            "error": None
        }
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the decision node with the provided inputs."""
        value = self.inputs["value"]
        condition = self.inputs.get("condition") or self.condition
        
        if value is None:
            error_msg = "No input value provided to Decision node"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
        
        if not condition:
            error_msg = "No condition specified for Decision node"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
        
        try:
            # Create a context with the input value
            context = {"input": value}
            
            # Evaluate the condition expression
            result = eval(condition, {"__builtins__": {}}, context)
            
            # Set the appropriate output port based on the condition result
            if result:
                self.outputs[self.true_port] = value
                self.outputs[self.false_port] = None
            else:
                self.outputs[self.true_port] = None
                self.outputs[self.false_port] = value
            
            return self.outputs
            
        except Exception as e:
            error_msg = f"Decision node execution error: {str(e)}"
            self.outputs["error"] = error_msg
            return {"error": error_msg}


# Register this node type with the registry
NodeRegistry.register("decision", DecisionNode)