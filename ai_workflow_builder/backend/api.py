"""
API endpoints for communication between the frontend and backend.
"""
import os
import json
import time
import secrets
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from jose import JWTError, jwt
from passlib.context import CryptContext

from .workflows import WorkflowRunner
from .state_manager import StateManager
from .nodes import NodeRegistry
from .nodes.tool_node import ToolRegistry
from ..shared.models import WorkflowConfig
from ..shared import logger

# Security settings
SECRET_KEY = os.environ.get("AI_WORKFLOW_BUILDER_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours
API_KEY_NAME = "X-API-Key"

# Create password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# API key header
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Create FastAPI app
app = FastAPI(
    title="AI Workflow Builder API",
    description="API for creating and executing AI workflows",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# State manager for checkpoints
state_manager = StateManager()

# In-memory cache for active workflows
active_workflows = {}

# In-memory rate limiting
rate_limits = {}

# Sample user database - in production, use a real database
fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "Administrator",
        "email": "admin@example.com",
        "hashed_password": pwd_context.hash("adminpassword"),
        "disabled": False,
    }
}

# Sample API keys - in production, use a real database
api_keys = {
    "12345": {"client": "admin"}
}


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware to prevent abuse.
    Limits to 100 requests per minute per client.
    """
    # Get client IP
    client_ip = request.client.host
    
    # Skip rate limiting for local requests
    if client_ip in ("127.0.0.1", "localhost", "::1"):
        return await call_next(request)
    
    # Initialize rate limit entry
    now = time.time()
    if client_ip not in rate_limits:
        rate_limits[client_ip] = {"count": 0, "reset_at": now + 60}
    
    # Reset count if needed
    if now > rate_limits[client_ip]["reset_at"]:
        rate_limits[client_ip] = {"count": 0, "reset_at": now + 60}
    
    # Check rate limit
    rate_limits[client_ip]["count"] += 1
    if rate_limits[client_ip]["count"] > 100:  # 100 requests per minute
        logger.warning(f"Rate limit exceeded for {client_ip}")
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Please try again later."}
        )
    
    # Continue with the request
    return await call_next(request)


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


# Authentication models
class Token(BaseModel):
    """Token model for authentication."""
    access_token: str
    token_type: str
    expires_at: datetime


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: Optional[str] = None
    exp: Optional[datetime] = None


class User(BaseModel):
    """User model."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    """User model with hashed password."""
    hashed_password: str


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


# Authentication functions
def verify_password(plain_password, hashed_password):
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """Generate password hash."""
    return pwd_context.hash(password)


def get_user(db, username: str):
    """Get user from database."""
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None


def authenticate_user(fake_db, username: str, password: str):
    """Authenticate user."""
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expires = datetime.utcnow() + expires_delta
    else:
        expires = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expires})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt, expires


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        token_data = TokenPayload(sub=username, exp=payload.get("exp"))
    except JWTError:
        raise credentials_exception
    
    user = get_user(fake_users_db, username=token_data.sub)
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Check if user is active."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key."""
    if api_key is None:
        return None
    
    if api_key not in api_keys:
        return None
    
    return api_keys[api_key]


async def get_auth_from_api_key_or_token(
    api_key_info: Optional[Dict] = Depends(verify_api_key),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Get authentication from either API key or JWT token."""
    if current_user:
        return current_user
    
    if api_key_info:
        username = api_key_info.get("client")
        if username:
            user = get_user(fake_users_db, username)
            if user:
                return user
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Authentication endpoints
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login to get access token."""
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    
    if not user:
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_data = {"sub": user.username}
    access_token, expires = create_access_token(access_token_data)
    
    logger.info(f"User {user.username} logged in successfully")
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_at=expires
    )


@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return current_user


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
async def validate_workflow(
    request: WorkflowRequest,
    current_user: User = Depends(get_auth_from_api_key_or_token)
):
    """
    Validate a workflow configuration.
    
    This endpoint checks if a workflow configuration is valid without executing it.
    """
    try:
        # Log validation attempt
        logger.info(f"Workflow validation request from user: {current_user.username}")
        
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
        
        logger.info(f"Workflow validated successfully by user: {current_user.username}")
        return {"valid": True}
    except Exception as e:
        logger.error(f"Workflow validation error: {str(e)}")
        return {"valid": False, "errors": str(e)}


@app.post("/workflow/execute", response_model=WorkflowResponse)
async def execute_workflow(
    request: WorkflowRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_auth_from_api_key_or_token)
):
    """
    Execute a workflow.
    
    This endpoint starts asynchronous execution of a workflow and returns
    a workflow ID that can be used to check the status.
    """
    try:
        # Validate the workflow first
        validation = await validate_workflow(request, current_user)
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
            "user": current_user.username,
            "started_at": datetime.utcnow(),
        }
        
        logger.info(f"Starting workflow execution {workflow_id} for user: {current_user.username}")
        
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
async def get_workflow_status(
    workflow_id: str,
    current_user: User = Depends(get_auth_from_api_key_or_token)
):
    """
    Get the status of a workflow.
    
    This endpoint returns the current status and results (if available)
    for a specific workflow execution.
    """
    if workflow_id not in active_workflows:
        logger.warning(f"Workflow {workflow_id} not found, requested by user: {current_user.username}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Workflow {workflow_id} not found"
        )
    
    workflow_info = active_workflows[workflow_id]
    
    # Check if user has access to this workflow
    if workflow_info.get("user") and workflow_info["user"] != current_user.username:
        logger.warning(f"User {current_user.username} attempted to access workflow {workflow_id} belonging to {workflow_info['user']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this workflow"
        )
    
    return WorkflowResponse(
        workflow_id=workflow_id,
        status=workflow_info["status"],
        results=workflow_info.get("results")
    )


@app.post("/workflow/save", response_model=CheckpointResponse)
async def save_workflow(
    request: WorkflowRequest,
    current_user: User = Depends(get_auth_from_api_key_or_token)
):
    """
    Save a workflow to a checkpoint.
    
    This endpoint saves a workflow configuration to a persistent checkpoint
    that can be loaded later.
    """
    try:
        # Validate workflow before saving
        validation = await validate_workflow(request, current_user)
        if not validation.get("valid", False):
            return CheckpointResponse(
                path="",
                success=False,
                message=f"Cannot save invalid workflow: {validation.get('errors', 'Unknown error')}"
            )
        
        # Add user metadata to the workflow
        workflow_with_metadata = request.workflow.copy()
        if "metadata" not in workflow_with_metadata:
            workflow_with_metadata["metadata"] = {}
        
        workflow_with_metadata["metadata"].update({
            "created_by": current_user.username,
            "created_at": datetime.utcnow().isoformat(),
            "last_modified_by": current_user.username,
            "last_modified_at": datetime.utcnow().isoformat(),
        })
        
        # Save the workflow
        path = state_manager.save(workflow_with_metadata)
        
        logger.info(f"Workflow saved to {path} by user: {current_user.username}")
        
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
async def list_checkpoints(
    current_user: User = Depends(get_auth_from_api_key_or_token)
):
    """
    List available checkpoints.
    
    This endpoint returns a list of all saved workflow checkpoints.
    """
    try:
        # Get checkpoints
        checkpoints = state_manager.get_checkpoints()
        
        # Filter checkpoints by user (if metadata is available)
        user_checkpoints = []
        for checkpoint in checkpoints:
            # Always include checkpoints without metadata
            if "metadata" not in checkpoint:
                user_checkpoints.append(checkpoint)
                continue
                
            # Include checkpoints created by the current user
            if checkpoint.get("metadata", {}).get("created_by") == current_user.username:
                user_checkpoints.append(checkpoint)
                continue
        
        logger.info(f"Retrieved {len(user_checkpoints)} checkpoints for user: {current_user.username}")
        
        return CheckpointListResponse(checkpoints=user_checkpoints)
        
    except Exception as e:
        logger.error(f"Error listing checkpoints: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error listing checkpoints: {str(e)}"
        )


@app.get("/workflow/load/{checkpoint_path:path}", response_model=Dict[str, Any])
async def load_checkpoint(
    checkpoint_path: str,
    current_user: User = Depends(get_auth_from_api_key_or_token)
):
    """
    Load a workflow from a checkpoint.
    
    This endpoint loads a saved workflow configuration from a checkpoint.
    """
    try:
        # Load the workflow
        workflow = state_manager.load(checkpoint_path)
        
        # Check user permissions (if metadata is available)
        if "metadata" in workflow:
            if workflow["metadata"].get("created_by") != current_user.username:
                logger.warning(f"User {current_user.username} attempted to load checkpoint {checkpoint_path} owned by {workflow['metadata'].get('created_by')}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to access this checkpoint"
                )
        
        logger.info(f"Checkpoint {checkpoint_path} loaded by user: {current_user.username}")
        
        return workflow
        
    except Exception as e:
        logger.error(f"Error loading checkpoint {checkpoint_path}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error loading checkpoint: {str(e)}"
        )


@app.get("/node_types", response_model=NodeTypesResponse)
async def get_node_types(
    current_user: User = Depends(get_auth_from_api_key_or_token)
):
    """
    Get available node types.
    
    This endpoint returns a list of all available node types that can be
    used in workflows.
    """
    try:
        # Get node types from the registry
        node_types = NodeRegistry.get_node_types()
        
        logger.info(f"Retrieved {len(node_types)} node types for user: {current_user.username}")
        
        return NodeTypesResponse(node_types=node_types)
        
    except Exception as e:
        logger.error(f"Error getting node types: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error getting node types: {str(e)}"
        )


@app.get("/tools", response_model=ToolsResponse)
async def get_tools(
    current_user: User = Depends(get_auth_from_api_key_or_token)
):
    """
    Get available tools.
    
    This endpoint returns a list of all available tools that can be used
    by Tool nodes in workflows.
    """
    try:
        # Get tools from the registry
        tools = ToolRegistry.get_tool_names()
        
        logger.info(f"Retrieved {len(tools)} tools for user: {current_user.username}")
        
        return ToolsResponse(tools=tools)
        
    except Exception as e:
        logger.error(f"Error getting tools: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error getting tools: {str(e)}"
        )


# Export ASGI app
app_asgi = app