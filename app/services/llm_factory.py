import logging
import base64
from typing import Any, Union, List, Dict
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage
from app.config import Config, LLMProvider
import json
import time
from anthropic import Anthropic, RateLimitError
from google.generativeai import types
import google.generativeai as genai
from openai import OpenAI
import PyPDF2

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
        1. How many pdfs did you receive?
        2. Can you see any bank transaction data and returned fee and overdraft fee data?
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
        logger.info(" Initialized Claude wrapper")

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
        logger.info(" Initialized Gemini wrapper")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            logger.info("➕ Adding new prompt to conversation")
            logger.debug(f"Prompt: {prompt[:100]}...")
            
            contents = []
            
            # Add file contents first if they exist
            if self.file_contents:
                for content in self.file_contents:
                    try:
                        with open(content['file_path'], 'rb') as file:
                            contents.append({
                                "mime_type": "application/pdf",
                                "data": file.read()
                            })
                    except Exception as e:
                        logger.error(f"Error processing PDF for Gemini: {str(e)}")
            
            # Add prompt
            contents.append(prompt)
            
            # Clear previous messages to prevent multiple tool calls
            self.messages = []
            
            logger.info(f"📨 Sending to Gemini with {len(contents)-1} PDFs")
            result = self.model.generate_content(contents)
            
            logger.info("📥 Received response from Gemini")
            logger.debug(f"Response: {result.text[:100]}...")
            return result.text

class OpenAIWrapper(LLMWrapper):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL  # "gpt-4-0125-preview"
        logger.info(f"🤖 Initialized OpenAI wrapper with model: {self.model}")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            logger.info("➕ Adding new prompt to conversation")
            logger.debug(f"Prompt preview: {str(prompt)[:100]}...")
            
            messages = []
            
            # Add file contents as text
            if self.file_contents:
                content_text = ""
                for content in self.file_contents:
                    try:
                        with open(content['file_path'], 'rb') as file:
                            pdf_reader = PyPDF2.PdfReader(file)
                            for page in pdf_reader.pages:
                                content_text += page.extract_text() + "\n\n"
                    except Exception as e:
                        logger.error(f"Error processing PDF: {str(e)}")
                
                if content_text:
                    messages.append({
                        "role": "user",
                        "content": f"Here are the bank statements:\n\n{content_text}"
                    })
            
            # Add the prompt
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            try:
                logger.info(f"📨 Sending to OpenAI with {len(messages)} messages")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=1000
                )
                logger.info("✅ OpenAI response received")
                return response.choices[0].message.content
                
            except Exception as e:
                logger.error(f"❌ Error from OpenAI: {str(e)}")
                raise

    def _bind_tools(self, tools: List[Any]):
        """Configure tools for OpenAI"""
        logger.info("🔧 Binding tools for OpenAI")
        self.tools = tools

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
            genai.configure(api_key=Config.GOOGLE_API_KEY)
            model = genai.GenerativeModel(Config.GEMINI_MODEL)
            return GeminiWrapper(model)
        elif provider == LLMProvider.OPENAI:
            return OpenAIWrapper()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")