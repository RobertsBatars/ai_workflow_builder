"""
State management system for saving and loading workflow states.
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..shared.models import StateCheckpoint, WorkflowConfig


class StateManager:
    """
    Manages saving and loading workflow states.
    Implements checkpointing and crash recovery.
    """
    def __init__(self, checkpoint_dir: str = None):
        """
        Initialize the state manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoint files.
                           Defaults to 'checkpoints' in the current directory.
        """
        self.checkpoint_dir = checkpoint_dir or os.path.join(os.getcwd(), "checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
    
    def save(self, workflow: Dict[str, Any], path: Optional[str] = None) -> str:
        """
        Save a workflow state to a file.
        
        Args:
            workflow: The workflow configuration to save.
            path: Optional path to save to. If not provided, a timestamped
                  path will be generated.
        
        Returns:
            The path where the state was saved.
        """
        if path is None:
            # Generate a timestamped filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(self.checkpoint_dir, f"workflow_{timestamp}.json")
        
        # Create the checkpoint object
        checkpoint = StateCheckpoint(
            workflow=WorkflowConfig.parse_obj(workflow),
            timestamp=time.time(),
            node_states={}  # Future: capture node states here
        )
        
        # Convert to a dictionary
        checkpoint_dict = checkpoint.dict()
        
        # Save to file
        with open(path, "w") as f:
            json.dump(checkpoint_dict, f, indent=2)
        
        return path
    
    def load(self, path: str) -> Dict[str, Any]:
        """
        Load a workflow state from a file.
        
        Args:
            path: Path to the state file.
        
        Returns:
            The loaded workflow configuration.
        """
        with open(path, "r") as f:
            checkpoint_dict = json.load(f)
        
        # Parse into a checkpoint object
        checkpoint = StateCheckpoint.parse_obj(checkpoint_dict)
        
        # Return the workflow configuration
        return checkpoint.workflow.dict()
    
    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """
        Get a list of available checkpoints.
        
        Returns:
            List of dictionaries with checkpoint info.
        """
        checkpoints = []
        
        # Find JSON files in the checkpoint directory
        for filename in os.listdir(self.checkpoint_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.checkpoint_dir, filename)
                
                try:
                    # Load the checkpoint
                    with open(path, "r") as f:
                        checkpoint_dict = json.load(f)
                    
                    # Get basic info
                    checkpoint_info = {
                        "path": path,
                        "filename": filename,
                        "timestamp": checkpoint_dict.get("timestamp", 0),
                        "datetime": datetime.fromtimestamp(
                            checkpoint_dict.get("timestamp", 0)
                        ).strftime("%Y-%m-%d %H:%M:%S"),
                        "workflow_name": checkpoint_dict.get("workflow", {}).get("name", "Untitled")
                    }
                    
                    checkpoints.append(checkpoint_info)
                except Exception as e:
                    print(f"Error loading checkpoint {path}: {str(e)}")
        
        # Sort by timestamp, newest first
        checkpoints.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return checkpoints
    
    def get_latest_checkpoint(self) -> Optional[str]:
        """
        Get the path to the latest checkpoint.
        
        Returns:
            Path to the latest checkpoint file, or None if no checkpoints exist.
        """
        checkpoints = self.get_checkpoints()
        
        if checkpoints:
            return checkpoints[0]["path"]
        
        return None
    
    def autosave(self, workflow: Dict[str, Any]) -> str:
        """
        Save a workflow state to an autosave file.
        
        Args:
            workflow: The workflow configuration to save.
        
        Returns:
            The path where the state was saved.
        """
        # Generate an autosave filename
        path = os.path.join(self.checkpoint_dir, "autosave.json")
        
        # Save the workflow
        return self.save(workflow, path)
    
    def load_autosave(self) -> Optional[Dict[str, Any]]:
        """
        Load the latest autosave if it exists.
        
        Returns:
            The loaded workflow configuration, or None if no autosave exists.
        """
        path = os.path.join(self.checkpoint_dir, "autosave.json")
        
        if os.path.exists(path):
            return self.load(path)
        
        return None