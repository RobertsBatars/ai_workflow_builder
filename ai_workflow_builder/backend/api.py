"""
API endpoints for communication between the frontend and backend.
"""
import os
import json
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .workflows import WorkflowRunner
from .state_manager import StateManager
from .nodes import NodeRegistry
from .nodes.tool_node import ToolRegistry
from ..shared.models import WorkflowConfig


# Create FastAPI app
app = FastAPI(title="AI Workflow Builder API")

# State manager for checkpoints
state_manager = StateManager()

# In-memory cache for active workflows
active_workflows = {}


# Input/output models
class WorkflowRequest(BaseModel):
    """Request model for workflow operations."""
    workflow: Dict[str, Any] = Field(...)
    input_data: Optional[Dict[str, Any]] = None


class WorkflowResponse(BaseModel):
    """Response model for workflow operations."""
    workflow_id: str
    status: str
    results: Optional[Dict[str, Any]] = None
    errors: Optional[Dict[str, Any]] = None


class CheckpointResponse(BaseModel):
    """Response model for checkpoint operations."""
    path: str
    success: bool
    message: str


class CheckpointListResponse(BaseModel):
    """Response model for listing checkpoints."""
    checkpoints: List[Dict[str, Any]]


class NodeTypesResponse(BaseModel):
    """Response model for node type information."""
    node_types: List[str]


class ToolsResponse(BaseModel):
    """Response model for tool information."""
    tools: List[str]


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AI Workflow Builder API"}


@app.post("/workflow/validate", response_model=Dict[str, Any])
async def validate_workflow(request: WorkflowRequest):
    """Validate a workflow configuration."""
    try:
        # Parse the workflow configuration
        config = WorkflowConfig.parse_obj(request.workflow)
        return {"valid": True}
    except Exception as e:
        return {"valid": False, "errors": str(e)}


@app.post("/workflow/execute", response_model=WorkflowResponse)
async def execute_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    """Execute a workflow."""
    try:
        # Create a unique ID for the workflow
        import uuid
        workflow_id = str(uuid.uuid4())
        
        # Store the workflow for later reference
        active_workflows[workflow_id] = {
            "config": request.workflow,
            "status": "running",
            "results": None
        }
        
        # Run the workflow in the background
        background_tasks.add_task(
            _run_workflow, 
            workflow_id, 
            request.workflow, 
            request.input_data
        )
        
        return WorkflowResponse(
            workflow_id=workflow_id,
            status="running"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _run_workflow(workflow_id: str, workflow: Dict[str, Any], input_data: Optional[Dict[str, Any]] = None):
    """Run a workflow in the background."""
    try:
        # Create a workflow runner
        runner = WorkflowRunner(workflow)
        
        # Execute the workflow
        results = await runner.execute(input_data)
        
        # Update the workflow status
        active_workflows[workflow_id] = {
            "config": workflow,
            "status": "completed",
            "results": results
        }
        
        # Autosave after successful execution
        state_manager.autosave(workflow)
        
    except Exception as e:
        # Update the workflow status on error
        active_workflows[workflow_id] = {
            "config": workflow,
            "status": "failed",
            "results": {"error": str(e)}
        }


@app.get("/workflow/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow_status(workflow_id: str):
    """Get the status of a workflow."""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    
    workflow_info = active_workflows[workflow_id]
    
    return WorkflowResponse(
        workflow_id=workflow_id,
        status=workflow_info["status"],
        results=workflow_info.get("results")
    )


@app.post("/workflow/save", response_model=CheckpointResponse)
async def save_workflow(request: WorkflowRequest):
    """Save a workflow to a checkpoint."""
    try:
        # Save the workflow
        path = state_manager.save(request.workflow)
        
        return CheckpointResponse(
            path=path,
            success=True,
            message=f"Workflow saved to {path}"
        )
        
    except Exception as e:
        return CheckpointResponse(
            path="",
            success=False,
            message=f"Error saving workflow: {str(e)}"
        )


@app.get("/workflow/checkpoints", response_model=CheckpointListResponse)
async def list_checkpoints():
    """List available checkpoints."""
    try:
        # Get checkpoints
        checkpoints = state_manager.get_checkpoints()
        
        return CheckpointListResponse(checkpoints=checkpoints)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflow/load/{checkpoint_path:path}", response_model=Dict[str, Any])
async def load_checkpoint(checkpoint_path: str):
    """Load a workflow from a checkpoint."""
    try:
        # Load the workflow
        workflow = state_manager.load(checkpoint_path)
        
        return workflow
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/node_types", response_model=NodeTypesResponse)
async def get_node_types():
    """Get available node types."""
    try:
        # Get node types from the registry
        node_types = NodeRegistry.get_node_types()
        
        return NodeTypesResponse(node_types=node_types)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools", response_model=ToolsResponse)
async def get_tools():
    """Get available tools."""
    try:
        # Get tools from the registry
        tools = ToolRegistry.get_tool_names()
        
        return ToolsResponse(tools=tools)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Export ASGI app
app_asgi = app