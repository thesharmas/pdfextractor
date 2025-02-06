import logging
from typing import Any, Union, List, Dict
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from app.config import Config, LLMProvider
import json
import base64
import time
from anthropic import Anthropic, RateLimitError
from google.generativeai import types

logger = logging.getLogger(__name__)

class LLMWrapper:
    """Base wrapper class for LLMs with conversation memory"""
    def __init__(self):
        self.file_contents = None
        self.messages = []
        self.tools = []

    def set_file_contents(self, contents: List[Dict[str, Any]]) -> None:
        """Set the file contents and verify they were received."""
        self.file_contents = contents
        
        # Verify content was received
        verification_prompt = """I've just shared some bank statements with you. 
        To verify you received them correctly:
        1. How many documents did you receive?
        2. Can you see any bank transaction data?
        Please be specific but brief."""
        
        logger.info("🔍 Verifying PDF content reception...")
        verification_response = self.get_response(prompt=verification_prompt)
        logger.info(f"✅ Content verification: {verification_response}")

    def set_tools(self, tools: List[Any]):
        """Configure tools for the LLM"""
        logger.info(f"🔧 Setting tools: {[t.name for t in tools]}")
        self._bind_tools(tools)
        return self

    def _bind_tools(self, tools: List[Any]):
        """Base implementation for binding tools"""
        logger.info(f"🔧 Binding tools: {[t.name for t in tools]}")
        self.tools = tools

    def get_response(self, prompt: str = None) -> str:
        raise NotImplementedError

class ClaudeWrapper(LLMWrapper):
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    
    def __init__(self, model: ChatAnthropic):
        super().__init__()
        self.model = model
        logger.info("�� Initialized Claude wrapper")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            logger.info("➕ Adding new prompt to conversation")
            logger.debug(f"Prompt preview: {str(prompt)[:100]}...")
            
            message_content = []
            
            # Add file contents first if they exist
            if self.file_contents:
                for content in self.file_contents:
                    try:
                        with open(content['file_path'], 'rb') as file:
                            pdf_data = base64.b64encode(file.read()).decode('utf-8')
                            
                        message_content.append({
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data
                            },
                            "cache_control": {"type": "ephemeral"}
                        })
                    except Exception as e:
                        logger.error(f"Error processing PDF: {str(e)}")
            
            # Add prompt
            message_content.append({
                "type": "text",
                "text": prompt
            })
            
            self.messages = [{
                "role": "user",
                "content": message_content
            }]
            
        logger.info(f"📨 Sending conversation to Claude")
        try:
            result = self.model.invoke(self.messages)
            logger.info("✅ Claude response received successfully")
            
            # Handle different response types
            if isinstance(result, AIMessage):
                return result.content
            elif hasattr(result, 'text'):
                return result.text
            else:
                return str(result)
                
        except RateLimitError as e:
            logger.error(f"🚫 Rate limit hit: {str(e)}")
            logger.error(f"Rate limit details: {e.response.headers if hasattr(e, 'response') else 'No details'}")
            raise
        except Exception as e:
            logger.error(f"❌ Error from Claude: {str(e)}")
            raise

class GeminiWrapper(LLMWrapper):
    def __init__(self, model: Any):
        super().__init__()
        self.model = model
        self.messages = []
        logger.info("�� Initialized Gemini wrapper")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            logger.info("➕ Adding new prompt to conversation")
            logger.debug(f"Prompt: {prompt[:100]}...")
            
            contents = []
            
            # Add file contents first if they exist
            if self.file_contents:
                for content in self.file_contents:
                    file_path = content['file_path']
                    logger.info(f"📄 Processing file: {file_path}")
                    
                    try:
                        with open(file_path, 'rb') as file:
                            contents.append({
                                "mime_type": "application/pdf",
                                "data": file.read()
                            })
                    except Exception as e:
                        logger.error(f"Error processing PDF for Gemini: {str(e)}")
                        logger.error(f"Attempted file path: {file_path}")
            
            # Add prompt
            contents.append(prompt)
            
            logger.info(f"📨 Sending to Gemini with {len(contents)-1} PDFs")
            result = self.model.generate_content(contents)
            
            logger.info("📥 Received response from Gemini")
            logger.debug(f"Response: {result.text[:100]}...")
            return result.text

class LLMFactory:
    @staticmethod
    def create_llm(provider: LLMProvider = None) -> LLMWrapper:
        """Factory method that produces wrapped LLM instances"""
        # Use provided provider or fall back to config
        provider = provider or Config.LLM_PROVIDER
        
        logger.info(f"🏭 Creating new LLM instance for provider: {provider}")
        
        if provider == LLMProvider.CLAUDE:
            model = ChatAnthropic(
                model=Config.CLAUDE_MODEL,
                anthropic_api_key=Config.ANTHROPIC_API_KEY,
                temperature=Config.TEMPERATURE
            )
            return ClaudeWrapper(model)
        elif provider == LLMProvider.GEMINI:
            import google.generativeai as genai
            genai.configure(api_key=Config.GOOGLE_API_KEY)
            model = genai.GenerativeModel(Config.GEMINI_MODEL)
            return GeminiWrapper(model)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")