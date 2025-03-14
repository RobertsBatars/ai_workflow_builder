"""
Composite node implementation for encapsulating sub-workflows.
"""
from typing import Dict, Any, List

from .base import BaseNode, NodeRegistry
from ...shared.models import CompositeNodeConfig
from ..workflows import WorkflowRunner


class CompositeNode(BaseNode):
    """
    Node for encapsulating sub-workflows into reusable components.
    Acts like a function that contains an entire workflow inside.
    """
    def __init__(self, config: CompositeNodeConfig):
        super().__init__(config)
        self.workflow_json = config.parameters.get("workflow_json", {})
        
        # Composite nodes have dynamic ports based on the sub-workflow
        self._determine_ports_from_workflow()
    
    def _determine_ports_from_workflow(self):
        """Analyze the workflow to determine input and output ports."""
        # Default ports if workflow is empty or invalid
        self.inputs = {"input": None}
        self.outputs = {"output": None, "error": None}
        
        # If we have a valid workflow JSON, extract the inputs and outputs
        if self.workflow_json and isinstance(self.workflow_json, dict):
            # For now, we create a simplified model:
            # - Any node without incoming connections is an input
            # - Any node without outgoing connections is an output
            
            # This would need more sophisticated implementation in a real system
            # where ports are explicitly defined in the sub-workflow
            
            # For demo implementation, we'll keep the default ports
            pass
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the composite node's sub-workflow."""
        try:
            # Get the input data
            input_data = self.inputs.get("input", {})
            
            if not self.workflow_json:
                error_msg = "No sub-workflow specified for Composite node"
                self.outputs["error"] = error_msg
                return {"error": error_msg}
            
            # Create a workflow runner for the sub-workflow
            runner = WorkflowRunner(self.workflow_json)
            
            # Execute the sub-workflow
            result = await runner.execute(input_data)
            
            # Set the outputs based on the workflow result
            if "error" in result and result["error"]:
                self.outputs["error"] = result["error"]
            else:
                self.outputs["output"] = result
                self.outputs["error"] = None
            
            return self.outputs
            
        except Exception as e:
            error_msg = f"Composite node execution error: {str(e)}"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the node to a dictionary, including the sub-workflow."""
        node_dict = super().to_dict()
        # Ensure the sub-workflow is included in the parameters
        node_dict["parameters"]["workflow_json"] = self.workflow_json
        return node_dict


# Register this node type with the registry
NodeRegistry.register("composite", CompositeNode)