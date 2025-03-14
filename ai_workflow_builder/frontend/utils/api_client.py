"""
API client for communicating with the backend API.
"""
import json
import time
import requests
from typing import Dict, Any, List, Optional


class APIClient:
    """
    Client for interacting with the backend API.
    Handles communication between the frontend and backend.
    """
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize the API client.
        
        Args:
            base_url: The base URL of the backend API.
        """
        self.base_url = base_url
    
    def validate_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a workflow configuration.
        
        Args:
            workflow: The workflow configuration to validate.
        
        Returns:
            Dictionary with validation result.
        """
        url = f"{self.base_url}/workflow/validate"
        
        try:
            response = requests.post(
                url,
                json={"workflow": workflow}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"valid": False, "errors": str(e)}
    
    def execute_workflow(self, workflow: Dict[str, Any], input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a workflow.
        
        Args:
            workflow: The workflow configuration to execute.
            input_data: Optional input data for the workflow.
        
        Returns:
            Dictionary with execution result.
        """
        url = f"{self.base_url}/workflow/execute"
        
        payload = {
            "workflow": workflow
        }
        
        if input_data is not None:
            payload["input_data"] = input_data
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    
    def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get the status of a workflow execution.
        
        Args:
            workflow_id: The ID of the workflow execution.
        
        Returns:
            Dictionary with workflow status.
        """
        url = f"{self.base_url}/workflow/{workflow_id}"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def save_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save a workflow to a checkpoint.
        
        Args:
            workflow: The workflow configuration to save.
        
        Returns:
            Dictionary with save result.
        """
        url = f"{self.base_url}/workflow/save"
        
        response = requests.post(
            url,
            json={"workflow": workflow}
        )
        response.raise_for_status()
        return response.json()
    
    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """
        Get a list of available checkpoints.
        
        Returns:
            List of checkpoint information.
        """
        url = f"{self.base_url}/workflow/checkpoints"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["checkpoints"]
    
    def load_checkpoint(self, checkpoint_path: str) -> Dict[str, Any]:
        """
        Load a workflow from a checkpoint.
        
        Args:
            checkpoint_path: The path to the checkpoint file.
        
        Returns:
            The loaded workflow configuration.
        """
        # URL encode the path
        import urllib.parse
        encoded_path = urllib.parse.quote(checkpoint_path)
        
        url = f"{self.base_url}/workflow/load/{encoded_path}"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_node_types(self) -> List[str]:
        """
        Get a list of available node types.
        
        Returns:
            List of node type names.
        """
        url = f"{self.base_url}/node_types"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["node_types"]
    
    def get_tools(self) -> List[str]:
        """
        Get a list of available tools.
        
        Returns:
            List of tool names.
        """
        url = f"{self.base_url}/tools"
        
        response = requests.get(url)
        response.raise_for_status()
        return response.json()["tools"]
        
    def wait_for_workflow(self, workflow_id: str, timeout: int = 300, poll_interval: int = 2) -> Dict[str, Any]:
        """
        Wait for a workflow to complete.
        
        Args:
            workflow_id: The ID of the workflow execution.
            timeout: Maximum time to wait in seconds.
            poll_interval: How often to check status in seconds.
        
        Returns:
            The final workflow status.
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_workflow_status(workflow_id)
            
            if status["status"] in ["completed", "failed"]:
                return status
            
            time.sleep(poll_interval)
        
        # Timeout reached
        return {
            "workflow_id": workflow_id,
            "status": "timeout",
            "error": f"Workflow execution timed out after {timeout} seconds"
        }