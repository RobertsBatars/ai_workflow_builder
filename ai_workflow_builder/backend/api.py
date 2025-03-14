"""
API endpoints for communication between the frontend and backend.
"""
import os
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Simple application running locally - no complex auth needed
from .workflows import WorkflowRunner
from .state_manager import StateManager
from .nodes import NodeRegistry
from .nodes.tool_node import ToolRegistry
from ..shared.models import WorkflowConfig
from ..shared import logger

# Simple development user - since app runs locally
DEV_USER = {
    "username": "dev_user",
    "email": "dev@example.com",
    "full_name": "Development User",
    "disabled": False
}

# Create FastAPI app
app = FastAPI(
    title="AI Workflow Builder API",
    description="API for creating and executing AI workflows",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# State manager for checkpoints
state_manager = StateManager()

# In-memory cache for active workflows
active_workflows = {}

# Logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests and responses"""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.4f}s")
    
    return response

# Simple authentication dependency for local development
async def get_current_user():
    """Get the current user - always returns the dev user for local development."""
    return DEV_USER


# API models
class User(BaseModel):
    """User model."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


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


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    timestamp: datetime


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


# Simple API endpoints for local development
@app.get("/users/me", response_model=User)
async def read_users_me():
    """Get current user information."""
    return DEV_USER


# Health and info endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "AI Workflow Builder API"}


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    # Get version from module
    from .. import __version__
    
    return HealthResponse(
        status="ok",
        version=__version__,
        timestamp=datetime.utcnow()
    )


@app.post("/workflow/validate", response_model=Dict[str, Any])
async def validate_workflow(request: WorkflowRequest):
    """
    Validate a workflow configuration.
    
    This endpoint checks if a workflow configuration is valid without executing it.
    """
    try:
        # Log validation attempt
        logger.info(f"Workflow validation request")
        
        # Parse the workflow configuration
        config = WorkflowConfig.parse_obj(request.workflow)
        
        # Additional validation - check if node types exist
        node_types = NodeRegistry.get_node_types()
        for node in config.nodes:
            if node.type not in node_types:
                return {"valid": False, "errors": f"Invalid node type: {node.type}"}
        
        # Validate connections - check if nodes and ports exist
        node_ids = [node.id for node in config.nodes]
        for conn in config.connections:
            if conn.source_node not in node_ids:
                return {"valid": False, "errors": f"Connection references non-existent source node: {conn.source_node}"}
            if conn.target_node not in node_ids:
                return {"valid": False, "errors": f"Connection references non-existent target node: {conn.target_node}"}
        
        # Check for cycles in the workflow
        try:
            temp_runner = WorkflowRunner(config)
            temp_runner._topological_sort()
        except ValueError as e:
            return {"valid": False, "errors": str(e)}
        
        logger.info("Workflow validated successfully")
        return {"valid": True}
    except Exception as e:
        logger.error(f"Workflow validation error: {str(e)}")
        return {"valid": False, "errors": str(e)}


@app.post("/workflow/execute", response_model=WorkflowResponse)
async def execute_workflow(
    request: WorkflowRequest, 
    background_tasks: BackgroundTasks
):
    """
    Execute a workflow.
    
    This endpoint starts asynchronous execution of a workflow and returns
    a workflow ID that can be used to check the status.
    """
    try:
        # Validate the workflow first
        validation = await validate_workflow(request)
        if not validation.get("valid", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Invalid workflow: {validation.get('errors', 'Unknown error')}"
            )
        
        # Create a unique ID for the workflow
        import uuid
        workflow_id = str(uuid.uuid4())
        
        # Store the workflow for later reference
        active_workflows[workflow_id] = {
            "config": request.workflow,
            "status": "running",
            "results": None,
            "started_at": datetime.utcnow(),
        }
        
        logger.info(f"Starting workflow execution {workflow_id}")
        
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
        logger.error(f"Error starting workflow execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error starting workflow: {str(e)}"
        )


async def _run_workflow(workflow_id: str, workflow: Dict[str, Any], input_data: Optional[Dict[str, Any]] = None):
    """Run a workflow in the background."""
    start_time = time.time()
    
    try:
        logger.info(f"Starting workflow execution: {workflow_id}")
        
        # Create a workflow runner
        runner = WorkflowRunner(workflow)
        
        # Execute the workflow
        results = await runner.execute(input_data)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Update the workflow status
        active_workflows[workflow_id].update({
            "status": "completed",
            "results": results,
            "completed_at": datetime.utcnow(),
            "execution_time": execution_time
        })
        
        logger.info(f"Workflow {workflow_id} completed successfully in {execution_time:.2f} seconds")
        
        # Autosave after successful execution
        state_manager.autosave(workflow)
        
    except Exception as e:
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Update the workflow status on error
        active_workflows[workflow_id].update({
            "status": "failed",
            "results": {"error": str(e)},
            "failed_at": datetime.utcnow(),
            "execution_time": execution_time
        })
        
        logger.error(f"Workflow {workflow_id} failed after {execution_time:.2f} seconds: {str(e)}")
    
    # Cleanup resources if needed
    # This would handle any resource cleanup for the workflow


@app.get("/workflow/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow_status(workflow_id: str):
    """
    Get the status of a workflow.
    
    This endpoint returns the current status and results (if available)
    for a specific workflow execution.
    """
    if workflow_id not in active_workflows:
        logger.warning(f"Workflow {workflow_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Workflow {workflow_id} not found"
        )
    
    workflow_info = active_workflows[workflow_id]
    
    return WorkflowResponse(
        workflow_id=workflow_id,
        status=workflow_info["status"],
        results=workflow_info.get("results")
    )


@app.post("/workflow/save", response_model=CheckpointResponse)
async def save_workflow(request: WorkflowRequest):
    """
    Save a workflow to a checkpoint.
    
    This endpoint saves a workflow configuration to a persistent checkpoint
    that can be loaded later.
    """
    try:
        # Validate workflow before saving
        validation = await validate_workflow(request)
        if not validation.get("valid", False):
            return CheckpointResponse(
                path="",
                success=False,
                message=f"Cannot save invalid workflow: {validation.get('errors', 'Unknown error')}"
            )
        
        # Add basic metadata to the workflow
        workflow_with_metadata = request.workflow.copy()
        if "metadata" not in workflow_with_metadata:
            workflow_with_metadata["metadata"] = {}
        
        workflow_with_metadata["metadata"].update({
            "created_at": datetime.utcnow().isoformat(),
            "last_modified_at": datetime.utcnow().isoformat(),
        })
        
        # Save the workflow
        path = state_manager.save(workflow_with_metadata)
        
        logger.info(f"Workflow saved to {path}")
        
        return CheckpointResponse(
            path=path,
            success=True,
            message=f"Workflow saved to {path}"
        )
        
    except Exception as e:
        logger.error(f"Error saving workflow: {str(e)}")
        return CheckpointResponse(
            path="",
            success=False,
            message=f"Error saving workflow: {str(e)}"
        )


@app.get("/workflow/checkpoints", response_model=CheckpointListResponse)
async def list_checkpoints():
    """
    List available checkpoints.
    
    This endpoint returns a list of all saved workflow checkpoints.
    """
    try:
        # Get checkpoints
        checkpoints = state_manager.get_checkpoints()
        
        logger.info(f"Retrieved {len(checkpoints)} checkpoints")
        
        return CheckpointListResponse(checkpoints=checkpoints)
        
    except Exception as e:
        logger.error(f"Error listing checkpoints: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error listing checkpoints: {str(e)}"
        )


@app.get("/workflow/load/{checkpoint_path:path}", response_model=Dict[str, Any])
async def load_checkpoint(checkpoint_path: str):
    """
    Load a workflow from a checkpoint.
    
    This endpoint loads a saved workflow configuration from a checkpoint.
    """
    try:
        # Load the workflow
        workflow = state_manager.load(checkpoint_path)
        
        logger.info(f"Checkpoint {checkpoint_path} loaded")
        
        return workflow
        
    except Exception as e:
        logger.error(f"Error loading checkpoint {checkpoint_path}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error loading checkpoint: {str(e)}"
        )


@app.get("/node_types", response_model=NodeTypesResponse)
async def get_node_types():
    """
    Get available node types.
    
    This endpoint returns a list of all available node types that can be
    used in workflows.
    """
    try:
        # Get node types from the registry
        node_types = NodeRegistry.get_node_types()
        
        logger.info(f"Retrieved {len(node_types)} node types")
        
        return NodeTypesResponse(node_types=node_types)
        
    except Exception as e:
        logger.error(f"Error getting node types: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error getting node types: {str(e)}"
        )


@app.get("/tools", response_model=ToolsResponse)
async def get_tools():
    """
    Get available tools.
    
    This endpoint returns a list of all available tools that can be used
    by Tool nodes in workflows.
    """
    try:
        # Get tools from the registry
        tools = ToolRegistry.get_tool_names()
        
        logger.info(f"Retrieved {len(tools)} tools")
        
        return ToolsResponse(tools=tools)
        
    except Exception as e:
        logger.error(f"Error getting tools: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error getting tools: {str(e)}"
        )


class WorkflowGenerationRequest(BaseModel):
    """Request model for workflow generation."""
    description: str
    model: str = "gpt-4"


@app.post("/workflow/generate", response_model=Dict[str, Any])
async def generate_workflow(request: WorkflowGenerationRequest):
    """
    Generate a workflow from a natural language description.
    
    This endpoint uses AI to convert a textual description into a workflow configuration.
    """
    try:
        logger.info(f"Generating workflow from description using {request.model}")
        
        # Generate workflow using WorkflowRunner
        workflow_data = await WorkflowRunner.generate_from_text(
            request.description, 
            request.model
        )
        
        logger.info(f"Successfully generated workflow with {len(workflow_data.get('nodes', []))} nodes")
        
        return workflow_data
        
    except Exception as e:
        logger.error(f"Error generating workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating workflow: {str(e)}"
        )


# Export ASGI app
app_asgi = app