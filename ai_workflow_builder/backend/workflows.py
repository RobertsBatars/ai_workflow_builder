"""
Workflow execution engine for running node-based workflows.
"""
import asyncio
import json
import time
from typing import Dict, Any, List, Set, Tuple, Optional, Deque
from collections import deque

from pydantic import ValidationError

from .nodes import NodeRegistry
from ..shared.models import WorkflowConfig, NodeConfig, Connection


class WorkflowRunner:
    """
    Engine for executing workflows defined as directed acyclic graphs (DAGs).
    Handles parallel execution, dependency order, and error handling.
    """
    def __init__(self, workflow_config: Dict[str, Any]):
        """
        Initialize the workflow runner with a workflow configuration.
        The configuration can be a dictionary or a WorkflowConfig object.
        """
        if isinstance(workflow_config, dict):
            try:
                self.config = WorkflowConfig.parse_obj(workflow_config)
            except ValidationError as e:
                raise ValueError(f"Invalid workflow configuration: {str(e)}")
        elif isinstance(workflow_config, WorkflowConfig):
            self.config = workflow_config
        else:
            raise TypeError("workflow_config must be a dict or WorkflowConfig object")
        
        # Nodes and connections
        self.nodes = {}
        self.connections = []
        
        # Load the workflow
        self._load_workflow()
    
    def _load_workflow(self):
        """Load the workflow nodes and connections from the configuration."""
        # Create node instances from configurations
        for node_config in self.config.nodes:
            try:
                self.nodes[node_config.id] = NodeRegistry.create(node_config)
            except Exception as e:
                raise ValueError(f"Error creating node '{node_config.id}': {str(e)}")
        
        # Store connections
        self.connections = self.config.connections
    
    def _build_dependency_graph(self) -> Dict[str, Set[str]]:
        """
        Build a dependency graph for the workflow.
        Returns a dictionary mapping node IDs to sets of node IDs they depend on.
        """
        dependencies = {node_id: set() for node_id in self.nodes}
        
        # For each connection, the target node depends on the source node
        for connection in self.connections:
            target_node = connection.target_node
            source_node = connection.source_node
            
            if target_node in dependencies:
                dependencies[target_node].add(source_node)
        
        return dependencies
    
    def _topological_sort(self) -> List[List[str]]:
        """
        Perform a topological sort of the workflow nodes.
        Returns a list of lists, where each inner list contains node IDs
        that can be executed in parallel at that stage.
        """
        # Build the dependency graph
        dependencies = self._build_dependency_graph()
        
        # Create a reverse map: for each node, which nodes depend on it
        dependents = {node_id: set() for node_id in self.nodes}
        for node_id, deps in dependencies.items():
            for dep in deps:
                dependents[dep].add(node_id)
        
        # Find nodes with no dependencies
        no_deps = [node_id for node_id, deps in dependencies.items() if not deps]
        
        # Result will be a list of lists
        result = []
        
        # Process nodes in dependency order
        while no_deps:
            # Add the current level to the result
            result.append(no_deps)
            
            # Find nodes that are now ready to process
            next_level = []
            for node_id in no_deps:
                # For each node that depends on this one
                for dependent in dependents[node_id]:
                    # Remove the dependency
                    dependencies[dependent].remove(node_id)
                    # If all dependencies are satisfied, add to next level
                    if not dependencies[dependent]:
                        next_level.append(dependent)
            
            # Move to the next level
            no_deps = next_level
        
        # Check for cycles
        unprocessed = [node_id for node_id, deps in dependencies.items() if deps]
        if unprocessed:
            raise ValueError(f"Workflow contains cycles involving nodes: {unprocessed}")
        
        return result
    
    def _connect_nodes(self):
        """Set up the connections between nodes."""
        # For each connection in the workflow
        for connection in self.connections:
            source_node_id = connection.source_node
            source_port = connection.source_port
            target_node_id = connection.target_node
            target_port = connection.target_port
            
            # Get the source and target nodes
            source_node = self.nodes.get(source_node_id)
            target_node = self.nodes.get(target_node_id)
            
            if not source_node:
                raise ValueError(f"Source node '{source_node_id}' not found")
            if not target_node:
                raise ValueError(f"Target node '{target_node_id}' not found")
            
            # Get the output from the source node
            try:
                output = source_node.get_output(source_port)
                # Set the input on the target node
                target_node.set_input(target_port, output)
            except Exception as e:
                print(f"Warning: Failed to connect {source_node_id}.{source_port} to {target_node_id}.{target_port}: {str(e)}")
    
    async def execute(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the workflow and return the final outputs.
        
        Args:
            input_data: Optional input data to provide to the workflow.
                        This will be passed to nodes with no incoming connections.
        
        Returns:
            Dictionary mapping node IDs to their output values.
        """
        # Reset all nodes
        for node in self.nodes.values():
            node.reset()
        
        # Handle input data - assign to nodes with no incoming connections
        if input_data:
            self._apply_input_data(input_data)
        
        # Get execution order (topological sort)
        execution_order = self._topological_sort()
        
        # Execute nodes in dependency order
        results = {}
        errors = {}
        
        for level in execution_order:
            # Execute nodes at this level in parallel
            level_tasks = []
            for node_id in level:
                node = self.nodes[node_id]
                level_tasks.append(self._execute_node(node))
            
            # Wait for all nodes at this level to complete
            level_results = await asyncio.gather(*level_tasks, return_exceptions=True)
            
            # Process results
            for i, node_id in enumerate(level):
                result = level_results[i]
                
                # Handle exceptions
                if isinstance(result, Exception):
                    errors[node_id] = str(result)
                    continue
                
                # Store successful results
                results[node_id] = result
                
                # Update node outputs for connections
                self._connect_nodes()
        
        # Compile and return the final results
        final_results = {
            "outputs": self._get_final_outputs(),
            "all_results": results,
            "errors": errors
        }
        
        if errors:
            final_results["has_errors"] = True
        
        return final_results
    
    async def _execute_node(self, node):
        """Execute a single node with retry logic."""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Execute the node
                result = await node.execute()
                return result
            except Exception as e:
                if attempt < max_retries - 1:
                    # Wait before retrying
                    await asyncio.sleep(retry_delay)
                    # Increase delay for next retry
                    retry_delay *= 2
                else:
                    # Max retries reached, propagate the exception
                    raise
    
    def _apply_input_data(self, input_data: Dict[str, Any]):
        """
        Apply input data to nodes with no incoming connections.
        """
        # Find nodes with no incoming connections
        incoming_connections = {}
        for connection in self.connections:
            target_id = connection.target_node
            if target_id not in incoming_connections:
                incoming_connections[target_id] = []
            incoming_connections[target_id].append(connection)
        
        # Apply input to nodes with no incoming connections
        for node_id, node in self.nodes.items():
            if node_id not in incoming_connections:
                # This is a source node, apply the input data
                if hasattr(node, 'set_input') and callable(node.set_input):
                    # Find the first input port
                    if node.input_ports:
                        node.set_input(node.input_ports[0], input_data)
    
    def _get_final_outputs(self) -> Dict[str, Any]:
        """
        Get the final outputs from nodes with no outgoing connections.
        These represent the workflow's outputs.
        """
        # Find nodes with no outgoing connections
        outgoing_connections = {}
        for connection in self.connections:
            source_id = connection.source_node
            if source_id not in outgoing_connections:
                outgoing_connections[source_id] = []
            outgoing_connections[source_id].append(connection)
        
        # Collect outputs from nodes with no outgoing connections
        outputs = {}
        for node_id, node in self.nodes.items():
            if node_id not in outgoing_connections:
                # This is a sink node, collect its outputs
                for port in node.output_ports:
                    outputs[f"{node_id}.{port}"] = node.get_output(port)
        
        return outputs
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the workflow to a dictionary representation."""
        return self.config.dict()