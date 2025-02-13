import logging
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime
import tiktoken
import inspect

logger = logging.getLogger(__name__)

@dataclass
class TokenUsage:
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    endpoint: str  # e.g., "chat/completions", "messages"
    model: str     # e.g., "gpt-4", "claude-3-sonnet"
    function_name: str  # Add function name for context

class TokenTracker:
    def __init__(self):
        self.history: List[TokenUsage] = []
        self._encoders: Dict[str, tiktoken.Encoding] = {}
        self.running_total = {
            'input_tokens': 0,
            'output_tokens': 0
        }
    
    def _get_encoder(self, model: str):
        """Get or create appropriate tokenizer for the model"""
        if model not in self._encoders:
            if "gpt" in model:
                self._encoders[model] = tiktoken.encoding_for_model(model)
            else:
                # Default to cl100k_base for non-OpenAI models
                self._encoders[model] = tiktoken.get_encoding("cl100k_base")
        return self._encoders[model]
    
    def count_tokens(self, text: str, model: str) -> int:
        """Count tokens in text for specific model"""
        try:
            encoder = self._get_encoder(model)
            return len(encoder.encode(text))
        except Exception as e:
            logger.warning(f"Error counting tokens: {str(e)}. Using character-based estimate.")
            return len(text) // 4  # Rough estimate
    
    def track_usage(self, input_text: str, output_text: str, model: str, endpoint: str, function_name: str = None):
        """Track token usage for an API call"""
        # Get calling function name if not provided
        if function_name is None:
            # Look up the call stack to find the tool function
            frame = inspect.currentframe()
            try:
                while frame:
                    if frame.f_code.co_name.startswith('check_') or \
                       frame.f_code.co_name.startswith('extract_') or \
                       frame.f_code.co_name.startswith('analyze_'):
                        function_name = frame.f_code.co_name
                        break
                    frame = frame.f_back
            finally:
                del frame  # Avoid reference cycles
            
            if not function_name:
                function_name = 'unknown_tool'
        
        input_tokens = self.count_tokens(input_text, model)
        output_tokens = self.count_tokens(output_text, model)
        
        usage = TokenUsage(
            timestamp=datetime.now(),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            endpoint=endpoint,
            model=model,
            function_name=function_name
        )
        
        self.history.append(usage)
        self.running_total['input_tokens'] += input_tokens
        self.running_total['output_tokens'] += output_tokens
        
        # Log running totals after each API call
        logger.info(f"🔄 API Call to {endpoint} ({model})")
        logger.info(f"  Function: {function_name}")
        logger.info(f"  This call: {input_tokens + output_tokens:,} tokens ({input_tokens:,} in, {output_tokens:,} out)")
        logger.info(f"  Running total: {self.get_running_total():,} tokens")
    
    def get_running_total(self) -> int:
        """Get current running total of tokens"""
        return self.running_total['input_tokens'] + self.running_total['output_tokens']
    
    def get_total_usage(self, model: str = None) -> Dict[str, int]:
        """Get total token usage, optionally filtered by model"""
        total_input = 0
        total_output = 0
        
        for usage in self.history:
            if model is None or usage.model == model:
                total_input += usage.input_tokens
                total_output += usage.output_tokens
        
        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_tokens": total_input + total_output
        }

# Global token tracker instance
token_tracker = TokenTracker() 