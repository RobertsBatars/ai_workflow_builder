"""
LLM node implementation for interacting with language models through LiteLLM.
"""
import json
from typing import Dict, Any, List, Optional

import litellm
from pydantic import ValidationError

from .base import BaseNode, NodeRegistry
from ...shared.models import LLMNodeConfig


class LLMNode(BaseNode):
    """
    Node for interacting with language models using LiteLLM.
    Supports a variety of models from different providers.
    """
    def __init__(self, config: LLMNodeConfig):
        super().__init__(config)
        self.model = config.parameters.get("model", "")
        self.system_prompt = config.parameters.get("system_prompt", "")
        self.temperature = config.parameters.get("temperature", 0.7)
        self.tools = config.parameters.get("tools", [])
        
        # Setup standard ports
        self.inputs = {
            "prompt": None,
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
            "tools": self.tools
        }
        
        self.outputs = {
            "response": None,
            "tool_calls": None,
            "error": None
        }
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the LLM node with the provided inputs."""
        prompt = self.inputs["prompt"]
        system_prompt = self.inputs.get("system_prompt") or self.system_prompt
        temperature = self.inputs.get("temperature") or self.temperature
        tools = self.inputs.get("tools") or self.tools
        
        if not prompt:
            error_msg = "No prompt provided to LLM node"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
        
        if not self.model:
            error_msg = "No model specified for LLM node"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
        
        # Format tools for the LLM if provided
        formatted_tools = None
        if tools:
            try:
                formatted_tools = self._format_tools(tools)
            except Exception as e:
                error_msg = f"Error formatting tools: {str(e)}"
                self.outputs["error"] = error_msg
                return {"error": error_msg}
        
        try:
            # Call the LLM through LiteLLM
            response = await self._call_llm(
                prompt, 
                system_prompt, 
                temperature,
                formatted_tools
            )
            
            # Process the response
            if formatted_tools and "tool_calls" in response:
                self.outputs["tool_calls"] = response["tool_calls"]
            
            self.outputs["response"] = response["content"]
            return self.outputs
            
        except Exception as e:
            error_msg = f"LLM execution error: {str(e)}"
            self.outputs["error"] = error_msg
            return {"error": error_msg}
    
    async def _call_llm(
        self, 
        prompt: str, 
        system_prompt: str, 
        temperature: float,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Make an async call to the LLM using LiteLLM."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Call with or without tools based on whether they're provided
        if tools:
            completion = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature,
                tools=tools
            )
        else:
            completion = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
        
        # Extract the result from the completion
        result = {
            "content": completion.choices[0].message.content
        }
        
        # Add tool calls if present
        if hasattr(completion.choices[0].message, "tool_calls") and completion.choices[0].message.tool_calls:
            result["tool_calls"] = completion.choices[0].message.tool_calls
        
        return result
    
    def _format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format tools into the structure expected by the LLM."""
        formatted_tools = []
        
        for tool in tools:
            formatted_tool = {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                }
            }
            
            # Add parameters schema if available
            if "parameters" in tool:
                formatted_tool["function"]["parameters"] = tool["parameters"]
            
            formatted_tools.append(formatted_tool)
        
        return formatted_tools


# Register this node type with the registry
NodeRegistry.register("llm", LLMNode)