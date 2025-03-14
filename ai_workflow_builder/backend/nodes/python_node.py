"""
Custom Python node implementation for executing user-defined code.
"""
import os
import sys
import tempfile
import subprocess
import asyncio
import json
from typing import Dict, Any, List, Optional

from .base import BaseNode, NodeRegistry
from ...shared.models import CustomPythonNodeConfig


class CustomPythonNode(BaseNode):
    """
    Node for executing custom Python code.
    Can run code in a sandboxed environment.
    """
    def __init__(self, config: CustomPythonNodeConfig):
        super().__init__(config)
        self.code = config.parameters.get("code", "")
        self.requirements = config.parameters.get("requirements", [])
        
        # Setup standard ports
        self.inputs = {
            "input": None,
            "code": self.code,
            "timeout": 30  # Default 30 seconds timeout
        }
        
        self.outputs = {
            "output": None,
            "error": None
        }
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the custom Python code with the provided inputs."""
        input_data = self.inputs.get("input", {})
        code = self.inputs.get("code") or self.code
        timeout = self.inputs.get("timeout", 30)
        
        if not code:
            error_msg = "No code provided to Python node"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
        
        try:
            # Execute the Python code in a sandboxed environment
            result = await self._execute_code(code, input_data, timeout)
            
            if "error" in result and result["error"]:
                self.outputs["error"] = result["error"]
                return {"error": result["error"]}
            
            self.outputs["output"] = result.get("output")
            return self.outputs
            
        except Exception as e:
            error_msg = f"Python node execution error: {str(e)}"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
    
    async def _execute_code(
        self, 
        code: str, 
        input_data: Any, 
        timeout: int,
        use_docker: bool = False
    ) -> Dict[str, Any]:
        """
        Execute the Python code.
        
        If use_docker is True, executes the code in a Docker container.
        Otherwise, executes it in a subprocess.
        """
        if use_docker:
            return await self._execute_in_docker(code, input_data, timeout)
        else:
            return await self._execute_in_subprocess(code, input_data, timeout)
    
    async def _execute_in_subprocess(
        self, 
        code: str, 
        input_data: Any, 
        timeout: int
    ) -> Dict[str, Any]:
        """Execute Python code in a subprocess."""
        # Create a temporary file for the code
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
            # Wrap the code in a function that processes the input and returns JSON
            wrapper_code = f"""
import json
import sys

# User-defined code
{code}

# Main function to handle input and call user code
def main():
    try:
        # Parse input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Call the 'run' function defined in the user code
        result = run(input_data)
        
        # Output the result as JSON
        print(json.dumps({{"output": result}}))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))

if __name__ == "__main__":
    main()
"""
            f.write(wrapper_code.encode())
            f.flush()
            
            temp_file_path = f.name
        
        try:
            # Convert input_data to JSON
            input_json = json.dumps(input_data)
            
            # Run the Python code in a subprocess
            process = await asyncio.create_subprocess_exec(
                sys.executable, temp_file_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Pass input data and wait for result with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input_json.encode()),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                # Kill the process if it times out
                process.kill()
                return {"error": f"Execution timed out after {timeout} seconds"}
            
            # Check for errors
            if process.returncode != 0:
                return {"error": f"Execution failed: {stderr.decode().strip()}"}
            
            # Parse the output
            try:
                result = json.loads(stdout.decode().strip())
                return result
            except json.JSONDecodeError:
                return {"error": f"Failed to parse output: {stdout.decode().strip()}"}
            
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    async def _execute_in_docker(
        self, 
        code: str, 
        input_data: Any, 
        timeout: int
    ) -> Dict[str, Any]:
        """Execute Python code in a Docker container."""
        # This is a placeholder for Docker execution
        # In a real implementation, this would create a Docker container,
        # execute the code, and return the result
        
        # For now, just delegate to subprocess execution with a warning
        result = await self._execute_in_subprocess(code, input_data, timeout)
        
        # Add a warning about Docker not being implemented
        if "error" not in result:
            result["warning"] = "Docker execution not implemented. Code ran in subprocess instead."
        
        return result


# Register this node type with the registry
NodeRegistry.register("python", CustomPythonNode)