"""
LLM node implementation for interacting with language models through LiteLLM.
"""
import json
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import litellm
from pydantic import ValidationError

# Try to import tiktoken, but provide a fallback if not available
try:
    import tiktoken
    tiktoken_available = True
except ImportError:
    print("Warning: tiktoken not available, using character-based token counting")
    tiktoken_available = False

from .base import BaseNode, NodeRegistry
from ...shared.models import LLMNodeConfig
from ...shared import logger


# Global rate limits for different LLM providers to avoid API rate limiting
_rate_limits = {
    "openai": {"last_call": 0, "min_interval": 0.5},  # 2 requests per second
    "anthropic": {"last_call": 0, "min_interval": 1.0},  # 1 request per second
    "cohere": {"last_call": 0, "min_interval": 1.5},  # ~0.7 requests per second
    "default": {"last_call": 0, "min_interval": 1.0},  # Default for other providers
}

# Global token counting cache to avoid recomputing token counts
_token_count_cache = {}

# Model mapping for token counting
_tokenizer_map = {
    "gpt-3.5-turbo": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "claude-": "cl100k_base",  # Claude models approximate
    "llama-": "cl100k_base",  # Llama models approximate
    "gemini-": "cl100k_base",  # Gemini models approximate
    "default": "cl100k_base",
}


class LLMNode(BaseNode):
    """
    Node for interacting with language models using LiteLLM.
    Supports a variety of models from different providers with token counting
    and rate limiting.
    """
    def __init__(self, config: LLMNodeConfig):
        super().__init__(config)
        self.model = config.parameters.get("model", "")
        self.system_prompt = config.parameters.get("system_prompt", "")
        self.temperature = config.parameters.get("temperature", 0.7)
        self.tools = config.parameters.get("tools", [])
        self.max_tokens = config.parameters.get("max_tokens", None)
        self.streaming = config.parameters.get("streaming", False)
        
        # Add tracking for token usage
        self.token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0
        }
        
        # Add execution metrics
        self.metrics = {
            "api_provider": self._get_provider_from_model(),
            "execution_time": 0,
            "rate_limited": False,
            "rate_limit_wait_time": 0,
            "attempts": 0,
            "timestamp": None
        }
        
        # Setup standard ports
        self.inputs = {
            "prompt": None,
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
            "tools": self.tools,
            "max_tokens": self.max_tokens
        }
        
        self.outputs = {
            "response": None,
            "tool_calls": None,
            "token_usage": None,
            "metrics": None,
            "error": None
        }
    
    def _get_provider_from_model(self) -> str:
        """Determine provider from model name."""
        model_lower = self.model.lower()
        
        if "gpt" in model_lower or model_lower.startswith("text-"):
            return "openai"
        elif "claude" in model_lower:
            return "anthropic"
        elif "llama" in model_lower:
            return "meta"
        elif "gemini" in model_lower:
            return "google"
        elif "command" in model_lower:
            return "cohere"
        elif "mistral" in model_lower:
            return "mistral"
        
        return "unknown"
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the LLM node with the provided inputs."""
        # Reset metrics for this execution
        self.metrics = {
            "api_provider": self._get_provider_from_model(),
            "execution_time": 0,
            "rate_limited": False,
            "rate_limit_wait_time": 0,
            "attempts": 0,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        start_time = time.time()
        
        prompt = self.inputs["prompt"]
        system_prompt = self.inputs.get("system_prompt") or self.system_prompt
        temperature = self.inputs.get("temperature") or self.temperature
        tools = self.inputs.get("tools") or self.tools
        max_tokens = self.inputs.get("max_tokens") or self.max_tokens
        
        if not prompt:
            error_msg = "No prompt provided to LLM node"
            self.outputs["error"] = error_msg
            logger.warning(f"LLM Node execution failed: {error_msg}")
            return {"error": error_msg}
        
        if not self.model:
            error_msg = "No model specified for LLM node"
            self.outputs["error"] = error_msg
            logger.warning(f"LLM Node execution failed: {error_msg}")
            return {"error": error_msg}
        
        # Format the messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # Count tokens in prompt
        try:
            prompt_tokens = self._count_tokens(messages)
            self.token_usage["prompt_tokens"] = prompt_tokens
            logger.debug(f"Prompt token count: {prompt_tokens}")
        except Exception as e:
            logger.warning(f"Error counting tokens: {str(e)}")
            # Continue even if token counting fails
            
        # Format tools for the LLM if provided
        formatted_tools = None
        if tools:
            try:
                formatted_tools = self._format_tools(tools)
            except Exception as e:
                error_msg = f"Error formatting tools: {str(e)}"
                self.outputs["error"] = error_msg
                logger.error(f"LLM Node tool formatting error: {error_msg}")
                return {"error": error_msg}
        
        try:
            # Call the LLM through LiteLLM with rate limiting and retries
            response = await self._call_llm_with_retries(
                messages, 
                temperature,
                formatted_tools,
                max_tokens
            )
            
            # Process the response
            if formatted_tools and "tool_calls" in response:
                self.outputs["tool_calls"] = response["tool_calls"]
            
            # Count completion tokens if available 
            if "completion_tokens" in response:
                self.token_usage["completion_tokens"] = response["completion_tokens"]
                self.token_usage["total_tokens"] = self.token_usage["prompt_tokens"] + response["completion_tokens"]
                
                # Calculate approximate cost
                self.token_usage["cost"] = self._calculate_cost(
                    self.token_usage["prompt_tokens"],
                    response["completion_tokens"]
                )
            
            # Set outputs
            self.outputs["response"] = response["content"]
            self.outputs["token_usage"] = self.token_usage
            
            # Calculate and set execution metrics
            self.metrics["execution_time"] = time.time() - start_time
            self.outputs["metrics"] = self.metrics
            
            logger.info(
                f"LLM Node executed successfully: model={self.model}, "
                f"tokens={self.token_usage['total_tokens']}, "
                f"time={self.metrics['execution_time']:.2f}s"
            )
            
            return self.outputs
            
        except Exception as e:
            error_msg = f"LLM execution error: {str(e)}"
            self.outputs["error"] = error_msg
            
            # Set metrics even on error
            self.metrics["execution_time"] = time.time() - start_time
            self.outputs["metrics"] = self.metrics
            
            logger.error(f"LLM Node execution failed: {error_msg}")
            return {"error": error_msg}
    
    async def _call_llm_with_retries(
        self, 
        messages: List[Dict[str, Any]],
        temperature: float,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Call LLM with rate limiting and retries."""
        max_retries = 3
        backoff_factor = 2
        provider = self._get_provider_from_model()
        
        for attempt in range(1, max_retries + 1):
            self.metrics["attempts"] = attempt
            
            try:
                # Apply rate limiting
                wait_time = self._apply_rate_limit(provider)
                if wait_time > 0:
                    self.metrics["rate_limited"] = True
                    self.metrics["rate_limit_wait_time"] += wait_time
                    logger.debug(f"Rate limiting applied for {provider}, waiting {wait_time:.2f}s")
                
                # Make the API call
                return await self._call_llm(messages, temperature, tools, max_tokens)
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for rate limit errors
                if "rate limit" in error_msg or "too many requests" in error_msg:
                    self.metrics["rate_limited"] = True
                    
                    # Exponential backoff
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Rate limit hit for {provider}, retrying in {wait_time}s (attempt {attempt}/{max_retries})")
                    
                    # Update rate limit settings dynamically
                    if provider in _rate_limits:
                        _rate_limits[provider]["min_interval"] *= 1.5  # Increase interval for future requests
                    
                    # Wait before retrying
                    await asyncio.sleep(wait_time)
                    self.metrics["rate_limit_wait_time"] += wait_time
                    continue
                
                # For other errors, if we have more retries, wait and try again
                if attempt < max_retries:
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"LLM call failed with error: {str(e)}, retrying in {wait_time}s (attempt {attempt}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                    
                # No more retries, raise the error
                logger.error(f"LLM call failed after {max_retries} attempts: {str(e)}")
                raise

    async def _call_llm(
        self, 
        messages: List[Dict[str, Any]],
        temperature: float,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make an async call to the LLM using LiteLLM."""
        # Base parameters
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        # Add optional parameters
        if max_tokens:
            params["max_tokens"] = max_tokens
        
        if tools:
            params["tools"] = tools
        
        # Call LiteLLM with the parameters
        completion = await litellm.acompletion(**params)
        
        # Extract the result from the completion
        result = {
            "content": completion.choices[0].message.content or ""  # Handle None content
        }
        
        # Add token usage information if available
        if hasattr(completion, "usage") and completion.usage:
            if hasattr(completion.usage, "completion_tokens"):
                result["completion_tokens"] = completion.usage.completion_tokens
            if hasattr(completion.usage, "prompt_tokens"):
                result["prompt_tokens"] = completion.usage.prompt_tokens
            if hasattr(completion.usage, "total_tokens"):
                result["total_tokens"] = completion.usage.total_tokens
        
        # Add tool calls if present
        if hasattr(completion.choices[0].message, "tool_calls") and completion.choices[0].message.tool_calls:
            result["tool_calls"] = completion.choices[0].message.tool_calls
        
        logger.debug(f"LLM call successful for model {self.model}")
        return result
    
    def _apply_rate_limit(self, provider: str) -> float:
        """
        Apply rate limiting for the provider.
        Returns the time waited (if any).
        """
        # Get rate limit settings for this provider or use default
        if provider in _rate_limits:
            rate_limit = _rate_limits[provider]
        else:
            rate_limit = _rate_limits["default"]
        
        # Calculate time since last call
        now = time.time()
        time_since_last_call = now - rate_limit["last_call"]
        
        # If we need to wait, sleep for the required time
        if time_since_last_call < rate_limit["min_interval"]:
            wait_time = rate_limit["min_interval"] - time_since_last_call
            time.sleep(wait_time)
            # Update last call time after waiting
            _rate_limits[provider]["last_call"] = time.time()
            return wait_time
        
        # No wait required, update last call time
        _rate_limits[provider]["last_call"] = now
        return 0.0
    
    def _count_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Count tokens in the messages using tiktoken if available, otherwise approximate."""
        # Get a key that represents these messages for caching
        message_key = str(hash(str(messages)))
        
        # Check cache first
        if message_key in _token_count_cache:
            return _token_count_cache[message_key]
        
        # If tiktoken is not available, use character-based approximation
        if not tiktoken_available:
            token_count = self._approximate_token_count(messages)
            _token_count_cache[message_key] = token_count
            return token_count
        
        # Get the tokenizer based on the model
        tokenizer_name = self._get_tokenizer_for_model()
        
        try:
            # Initialize the tokenizer
            tokenizer = tiktoken.get_encoding(tokenizer_name)
            
            # Count tokens
            token_count = 0
            for message in messages:
                # Count content tokens
                if "content" in message and message["content"]:
                    token_count += len(tokenizer.encode(message["content"]))
                
                # Add overhead for message formatting (approximate)
                token_count += 4  # Overhead for message format
            
            # Add final overhead
            token_count += 2  # Final overhead
            
            # Cache the result
            _token_count_cache[message_key] = token_count
            
            return token_count
            
        except Exception as e:
            logger.warning(f"Error counting tokens: {str(e)}")
            # Return an approximate count based on characters if tokenizer fails
            return self._approximate_token_count(messages)
    
    def _get_tokenizer_for_model(self) -> str:
        """Get the appropriate tokenizer name for the model."""
        model_lower = self.model.lower()
        
        # Check for exact matches
        for model_prefix, tokenizer in _tokenizer_map.items():
            if model_lower.startswith(model_prefix):
                return tokenizer
        
        # Default to cl100k_base (GPT-4 tokenizer) which is a reasonable fallback
        return _tokenizer_map["default"]
    
    def _approximate_token_count(self, messages: List[Dict[str, Any]]) -> int:
        """Approximate token count when tokenizer is unavailable."""
        # Simple approximation: 1 token ~= 4 characters
        total_chars = 0
        for message in messages:
            if "content" in message and message["content"]:
                total_chars += len(message["content"])
        
        return total_chars // 4 + 20  # Add overhead
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate the approximate cost of the LLM call."""
        model_lower = self.model.lower()
        
        # Define cost per 1000 tokens for various models
        # Format: {model_prefix: (prompt_cost_per_1k, completion_cost_per_1k)}
        cost_map = {
            "gpt-4": (0.03, 0.06),            # GPT-4
            "gpt-4-turbo": (0.01, 0.03),      # GPT-4 Turbo
            "gpt-3.5-turbo": (0.0015, 0.002), # GPT-3.5 Turbo
            "claude-2": (0.011, 0.032),       # Claude 2
            "claude-3-opus": (0.015, 0.075),  # Claude 3 Opus
            "claude-3-sonnet": (0.003, 0.015),# Claude 3 Sonnet
            "claude-3-haiku": (0.00025, 0.00125), # Claude 3 Haiku
            "gemini-pro": (0.0005, 0.0015),   # Gemini Pro
            "llama-2": (0.0005, 0.0005),      # Llama 2 (approximate)
            "default": (0.002, 0.002)         # Default fallback
        }
        
        # Find matching model
        prompt_cost_per_1k = cost_map["default"][0]
        completion_cost_per_1k = cost_map["default"][1]
        
        for model_prefix, costs in cost_map.items():
            if model_lower.startswith(model_prefix):
                prompt_cost_per_1k, completion_cost_per_1k = costs
                break
        
        # Calculate total cost
        prompt_cost = (prompt_tokens / 1000) * prompt_cost_per_1k
        completion_cost = (completion_tokens / 1000) * completion_cost_per_1k
        total_cost = prompt_cost + completion_cost
        
        return round(total_cost, 6)  # Round to 6 decimal places
    
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