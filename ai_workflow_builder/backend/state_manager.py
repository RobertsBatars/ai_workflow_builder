"""
State management system for saving and loading workflow states.
"""
import os
import json
import time
import threading
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

import watchdog.events
import watchdog.observers
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..shared.models import StateCheckpoint, WorkflowConfig
from ..shared import logger


class FileChangeHandler(FileSystemEventHandler):
    """Handler for file system events."""
    def __init__(self, callback: Callable):
        self.callback = callback
        
    def on_modified(self, event):
        if not event.is_directory:
            self.callback(event.src_path)


class StateManager:
    """
    Manages saving and loading workflow states.
    Implements checkpointing, crash recovery, and autosave.
    """
    def __init__(self, checkpoint_dir: str = None, autosave_interval: int = 300):
        """
        Initialize the state manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoint files.
                           Defaults to 'checkpoints' in the current directory.
            autosave_interval: Interval in seconds for autosaving (default: 5 minutes)
        """
        self.checkpoint_dir = checkpoint_dir or os.path.join(os.getcwd(), "checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        # Current workflow and modification time
        self.current_workflow = None
        self.last_modified_time = 0
        self.last_autosave_time = 0
        self.autosave_interval = autosave_interval
        
        # File system observer for detecting changes
        self.observer = None
        self.file_handler = None
        
        # Autosave timer
        self.autosave_timer = None
        self.running = False
        
        # Start the autosave timer
        self._start_autosave_timer()
        
        # Check for crash recovery on startup
        self._check_for_crash_recovery()
    
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
        
        try:
            # Make sure checkpoint directory exists
            os.makedirs(self.checkpoint_dir, exist_ok=True)
            
            # Find JSON files in the checkpoint directory
            for filename in os.listdir(self.checkpoint_dir):
                if filename.endswith(".json"):
                    path = os.path.join(self.checkpoint_dir, filename)
                    
                    try:
                        # Load the checkpoint
                        with open(path, "r") as f:
                            checkpoint_dict = json.load(f)
                        
                        # Get basic info
                        timestamp = checkpoint_dict.get("timestamp", 0)
                        if isinstance(timestamp, str):
                            try:
                                timestamp = float(timestamp)
                            except ValueError:
                                timestamp = 0
                        
                        checkpoint_info = {
                            "path": path,
                            "filename": filename,
                            "timestamp": timestamp,
                            "datetime": datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                            "workflow_name": (checkpoint_dict.get("workflow", {}).get("name", None) or 
                                             checkpoint_dict.get("workflow", {}).get("metadata", {}).get("name", "Untitled"))
                        }
                        
                        checkpoints.append(checkpoint_info)
                    except Exception as e:
                        logger.error(f"Error loading checkpoint {path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error accessing checkpoint directory: {str(e)}")
        
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
        # Update current workflow
        self.current_workflow = workflow
        self.last_modified_time = time.time()
        
        # Generate an autosave filename
        path = os.path.join(self.checkpoint_dir, "autosave.json")
        
        try:
            # Save the workflow
            saved_path = self.save(workflow, path)
            self.last_autosave_time = time.time()
            logger.info(f"Workflow autosaved to {saved_path}")
            return saved_path
        except Exception as e:
            logger.error(f"Error autosaving workflow: {str(e)}")
            traceback.print_exc()
            return ""
    
    def load_autosave(self) -> Optional[Dict[str, Any]]:
        """
        Load the latest autosave if it exists.
        
        Returns:
            The loaded workflow configuration, or None if no autosave exists.
        """
        path = os.path.join(self.checkpoint_dir, "autosave.json")
        
        if os.path.exists(path):
            try:
                workflow = self.load(path)
                self.current_workflow = workflow
                logger.info(f"Loaded autosave from {path}")
                return workflow
            except Exception as e:
                logger.error(f"Error loading autosave: {str(e)}")
                return None
        
        return None
    
    def _start_autosave_timer(self):
        """Start the autosave timer."""
        if self.autosave_timer is not None:
            return
            
        self.running = True
        
        def autosave_loop():
            while self.running:
                time.sleep(min(30, self.autosave_interval))  # Check every 30 seconds or less
                
                try:
                    current_time = time.time()
                    
                    # Check if it's time to autosave
                    if (self.current_workflow is not None and 
                        current_time - self.last_autosave_time >= self.autosave_interval and
                        self.last_modified_time > self.last_autosave_time):
                        
                        logger.info("Performing periodic autosave")
                        self.autosave(self.current_workflow)
                except Exception as e:
                    logger.error(f"Error in autosave timer: {str(e)}")
        
        # Start the timer thread
        self.autosave_timer = threading.Thread(target=autosave_loop, daemon=True)
        self.autosave_timer.start()
        logger.info(f"Autosave timer started (interval: {self.autosave_interval}s)")
    
    def _stop_autosave_timer(self):
        """Stop the autosave timer."""
        self.running = False
        if self.autosave_timer is not None:
            self.autosave_timer.join(timeout=1.0)
            self.autosave_timer = None
    
    def _start_file_monitoring(self, directory: str):
        """
        Start monitoring file changes in a directory.
        
        Args:
            directory: Directory to monitor
        """
        if self.observer is not None:
            return
            
        # Create a file handler
        self.file_handler = FileChangeHandler(self._on_file_changed)
        
        # Create and start the observer
        self.observer = Observer()
        self.observer.schedule(self.file_handler, directory, recursive=True)
        self.observer.start()
        logger.info(f"File monitoring started for {directory}")
    
    def _stop_file_monitoring(self):
        """Stop file monitoring."""
        if self.observer is not None:
            self.observer.stop()
            self.observer.join()
            self.observer = None
    
    def _on_file_changed(self, path: str):
        """
        Handle file change events.
        
        Args:
            path: Path to the changed file
        """
        # Only handle relevant files (this would be customized based on what files to monitor)
        if self.current_workflow is None:
            return
            
        # Mark as modified
        self.last_modified_time = time.time()
        logger.debug(f"File changed: {path}")
    
    def _check_for_crash_recovery(self):
        """Check for an autosave file on startup and offer recovery."""
        autosave_path = os.path.join(self.checkpoint_dir, "autosave.json")
        
        if os.path.exists(autosave_path):
            try:
                # Get modification time of the autosave file
                mtime = os.path.getmtime(autosave_path)
                age = time.time() - mtime
                
                # Only consider recent autosaves (less than 1 day old)
                if age < 86400:  # 24 hours
                    formatted_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"Found autosave file from {formatted_time} - available for recovery")
                    
                    # Note: The actual recovery would be initiated from the UI
            except Exception as e:
                logger.error(f"Error checking crash recovery: {str(e)}")
    
    def __del__(self):
        """Clean up resources."""
        self._stop_autosave_timer()
        self._stop_file_monitoring()