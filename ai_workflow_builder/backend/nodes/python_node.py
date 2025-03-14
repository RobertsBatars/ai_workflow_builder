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
        
        # Get virtualization settings from workflow config
        if hasattr(self.config, '_workflow_config') and self.config._workflow_config:
            virtualization = self.config._workflow_config.environment.type
        else:
            # Default to lightweight virtualization if not specified
            virtualization = "lightweight"
        
        if not code:
            error_msg = "No code provided to Python node"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
        
        try:
            # Execute the Python code in a sandboxed environment
            result = await self._execute_code(code, input_data, timeout, virtualization)
            
            # Include any warnings in the output
            if "warning" in result:
                self.outputs["warning"] = result["warning"]
            
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
        virtualization: str = "lightweight"
    ) -> Dict[str, Any]:
        """
        Execute the Python code.
        
        Args:
            code: The Python code to execute
            input_data: The input data to pass to the code
            timeout: Timeout in seconds
            virtualization: Virtualization type ("none", "lightweight", "ubuntu")
            
        Returns:
            Dictionary with execution result
        """
        # Use Docker only if not set to "none"
        if virtualization != "none":
            try:
                return await self._execute_in_docker(code, input_data, timeout, virtualization)
            except Exception as e:
                # If Docker execution fails, fall back to subprocess with a warning
                result = await self._execute_in_subprocess(code, input_data, timeout)
                result["warning"] = f"Docker execution failed: {str(e)}. Code ran in subprocess instead."
                return result
        else:
            # If virtualization is explicitly set to "none"
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
        timeout: int,
        virtualization_type: str = "lightweight"
    ) -> Dict[str, Any]:
        """
        Execute Python code in a Docker container.
        
        Args:
            code: The Python code to execute
            input_data: The input data to pass to the code
            timeout: Timeout in seconds
            virtualization_type: Type of virtualization ("none", "lightweight", "ubuntu")
            
        Returns:
            Dictionary with execution result
        """
        try:
            # Import Docker SDK
            import docker
            from docker.errors import DockerException, ImageNotFound, APIError
        except ImportError:
            # Fall back to subprocess if Docker SDK is not available
            result = await self._execute_in_subprocess(code, input_data, timeout)
            result["warning"] = "Docker SDK not available. Code ran in subprocess instead."
            return result
        
        # Define Docker image based on virtualization type
        docker_image = {
            "none": None,  # Will fall back to subprocess
            "lightweight": "python:3.9-slim",
            "ubuntu": "python:3.9-bullseye"  # Debian-based with more utilities
        }.get(virtualization_type, "python:3.9-slim")
        
        # If virtualization is set to none, fall back to subprocess
        if docker_image is None:
            result = await self._execute_in_subprocess(code, input_data, timeout)
            result["warning"] = "Virtualization set to 'none'. Code ran in subprocess instead."
            return result
        
        # Create a Docker client
        try:
            client = docker.from_env()
        except DockerException as e:
            # Fall back to subprocess if Docker is not available
            result = await self._execute_in_subprocess(code, input_data, timeout)
            result["warning"] = f"Failed to connect to Docker: {str(e)}. Code ran in subprocess instead."
            return result
        
        # Create a temporary directory for files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a Python file with the code
            script_path = os.path.join(temp_dir, "script.py")
            
            # Create the wrapper script
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
            with open(script_path, "w") as f:
                f.write(wrapper_code)
            
            # Create requirements.txt if there are requirements
            requirements_path = None
            if self.requirements:
                requirements_path = os.path.join(temp_dir, "requirements.txt")
                with open(requirements_path, "w") as f:
                    for req in self.requirements:
                        f.write(f"{req}\n")
            
            # Create input.json file
            input_path = os.path.join(temp_dir, "input.json")
            with open(input_path, "w") as f:
                json.dump(input_data, f)
            
            # Define container configuration
            container_config = {
                "volumes": {
                    os.path.abspath(temp_dir): {
                        "bind": "/app",
                        "mode": "rw"
                    }
                },
                "working_dir": "/app",
                "command": "python script.py < input.json",
                "detach": True,
                "stderr": True,
                "stdout": True,
                "network_disabled": True,  # Disable network access for security
                "mem_limit": "512m",      # Limit memory usage
                "cpu_quota": 50000        # Limit CPU usage (50% of one core)
            }
            
            # Create and run the container
            try:
                container = client.containers.run(
                    docker_image,
                    **container_config
                )
                
                # Wait for container to finish with timeout
                try:
                    # Use asyncio to implement the timeout
                    async def wait_for_container():
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(None, container.wait)
                    
                    container_result = await asyncio.wait_for(
                        wait_for_container(), 
                        timeout=timeout
                    )
                    
                    # Get container logs
                    stdout = container.logs(stdout=True, stderr=False).decode()
                    stderr = container.logs(stdout=False, stderr=True).decode()
                    
                    # Check exit code
                    if container_result["StatusCode"] != 0:
                        return {"error": f"Execution failed: {stderr.strip()}"}
                    
                    # Parse the output
                    try:
                        result = json.loads(stdout.strip())
                        return result
                    except json.JSONDecodeError:
                        return {"error": f"Failed to parse output: {stdout.strip()}"}
                    
                except asyncio.TimeoutError:
                    return {"error": f"Execution timed out after {timeout} seconds"}
                
            except (DockerException, ImageNotFound, APIError) as e:
                return {"error": f"Docker execution error: {str(e)}"}
            
            finally:
                # Always clean up the container
                try:
                    container.remove(force=True)
                except:
                    pass  # Ignore cleanup errors


# Register this node type with the registry
NodeRegistry.register("python", CustomPythonNode)