import logging
import base64
from typing import Any, Union, List, Dict
import inspect
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
import pathlib
from app.services.rate_limiter import RATE_LIMITERS
from collections import defaultdict

logger = logging.getLogger(__name__)

class LLMWrapper:
    """Base wrapper class for LLMs with conversation memory"""
    def __init__(self):
        self.file_contents = None
        self.first_call = True

    def set_file_contents(self, contents: List[Dict[str, Any]]) -> None:
        """Set the file contents and verify they were received."""
        self.file_contents = contents
        
        verification_prompt = """I've just shared some bank statements with you. 
        verify that you received them correctly and that you can see the data in the pdfs.
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
    def __init__(self):
        super().__init__()
        self.model = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.messages = []  # Store conversation history
        logger.info("🤖 Initialized Claude wrapper")

    def get_response(self, prompt: str = None) -> str:
        try:
            if not prompt:
                return ""
            
            # Only process PDFs on first call
            if self.first_call and self.file_contents:
                logger.info("📄 First call - processing PDFs")
                message_content = []
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
                                }
                            })
                    except Exception as e:
                        logger.error(f"Error processing PDF: {str(e)}")
                
                # Add PDF content to messages
                self.messages.append({
                    "role": "user",
                    "content": message_content
                })
                self.first_call = False
                logger.info("📨 First call - sent PDFs to Claude")
            
            # Add new prompt to messages
            self.messages.append({
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            })
            
            # Get response using messages.create
            result = self.model.messages.create(
                model=Config.CLAUDE_MODEL,
                messages=self.messages,
                max_tokens=Config.CLAUDE_MAX_TOKENS,
                temperature=Config.TEMPERATURE
            )
            
            # Add response to conversation history
            response_text = result.content[0].text
            self.messages.append({
                "role": "assistant",
                "content": response_text
            })
            
            return response_text
            
        except Exception as e:
            logger.error(f"❌ Error from Claude: {str(e)}")
            raise

class GeminiWrapper(LLMWrapper):
    def __init__(self):
        super().__init__()
        genai.configure(api_key=Config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(Config.GEMINI_MODEL)
        self.first_call = True
        self.chat = self.model.start_chat()
        self.rate_limiter = RATE_LIMITERS["gemini"]
        self.last_total_tokens = 0  # Track previous total for delta calculation
        logger.info(f"🤖 Initialized Gemini wrapper with model: {Config.GEMINI_MODEL}")

    def get_response(self, prompt: str = None) -> str:
        try:
            if not prompt:
                return ""
            
            # Only process PDFs on first call
            if self.first_call and self.file_contents:
                logger.info("📄 First call - processing PDFs")
                contents = ""
                for content in self.file_contents:
                    try:
                        with open(content['file_path'], 'rb') as file:
                            pdf_reader = PyPDF2.PdfReader(file)
                            for page in pdf_reader.pages:
                                contents += page.extract_text() + "\n\n"
                    except Exception as e:
                        logger.error(f"Error processing PDF: {str(e)}")
                
                if contents:
                    # Send PDF content only once
                    pdf_response = self.chat.send_message(
                        f"Here are the bank statements. Please acknowledge receipt with a brief confirmation:\n\n{contents}"
                    )
                
                self.first_call = False
                logger.info("📨 First call - sent PDFs to Gemini")
            
            # Send the prompt
            response = self.chat.send_message(prompt)
            
            response_text = response.text
            
            if response_text.count('{') != response_text.count('}'):
                logger.warning("⚠️ Incomplete JSON detected, requesting completion")
                completion = self.chat.send_message(
                    "Please complete the JSON response. Return ONLY the complete JSON."
                )
                
                response_text = completion.text
            
            return response_text
            
        except Exception as e:
            if "429" in str(e):
                logger.warning(f"🚫 Gemini rate limit hit, retrying...")
            logger.error(f"❌ Error from Gemini: {str(e)}")
            raise

class OpenAIWrapper(LLMWrapper):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL
        self.messages = []  # Store conversation history
        self.rate_limiter = RATE_LIMITERS["openai"]
        logger.info(f"🤖 Initialized OpenAI wrapper with model: {self.model}")

    def get_response(self, prompt: str = None) -> str:
        try:
            if not prompt:
                return ""
            
            # Only process PDFs on first call
            if self.first_call and self.file_contents:
                logger.info("📄 First call - processing PDFs")
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
                    # Add PDF content to conversation history
                    self.messages.append({
                        "role": "user",
                        "content": f"Here are the bank statements:\n\n{content_text}"
                    })
                
                self.first_call = False
                logger.info("📨 First call - sent PDFs to OpenAI")
            
            # Add new prompt to conversation history
            self.messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Get response using full conversation history
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                max_tokens=Config.OPENAI_MAX_TOKENS,
                temperature=Config.TEMPERATURE
            )
            
            # Add response to conversation history
            response_text = response.choices[0].message.content
            self.messages.append({
                "role": "assistant",
                "content": response_text
            })
            
            return response_text
            
        except Exception as e:
            logger.error(f"❌ Error in OpenAI wrapper: {str(e)}")
            raise

    def _bind_tools(self, tools: List[Any]):
        """Configure tools for OpenAI"""
        logger.info("🔧 Binding tools for OpenAI")
        self.tools = tools

class LLMFactory:
    @staticmethod
    def create_llm(provider: LLMProvider = None) -> LLMWrapper:
        """Factory method that produces wrapped LLM instances"""
        provider = provider or Config.LLM_PROVIDER
        
        logger.info(f"🏭 Creating new LLM instance for provider: {provider}")
        
        if provider == LLMProvider.CLAUDE:
            return ClaudeWrapper()
        elif provider == LLMProvider.GEMINI:
            return GeminiWrapper()
        elif provider == LLMProvider.OPENAI:
            return OpenAIWrapper()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")