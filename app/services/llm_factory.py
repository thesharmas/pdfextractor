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
import pathlib

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
    def __init__(self, model: ChatAnthropic):
        super().__init__()
        self.model = model
        self.first_call = True
        self.messages = []
        logger.info("🤖 Initialized Claude wrapper")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            message_content = []
            
            if self.first_call and self.file_contents:
                logger.info("📄 First call - processing PDFs")
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
                self.first_call = False
            
            # Add prompt
            message_content.append({
                "type": "text",
                "text": prompt
            })
            
            # Append to message history
            self.messages.append({
                "role": "user",
                "content": message_content
            })
            
        try:
            # Set max_tokens to a higher value
            result = self.model.invoke(
                self.messages,
                max_tokens=4096,  # Increase token limit
                temperature=0.7
            )
            
            # Store assistant's response
            self.messages.append({
                "role": "assistant",
                "content": result.content
            })
            
            # Validate response completeness for JSON
            response_text = result.content
            if response_text.count('{') != response_text.count('}'):
                logger.warning("⚠️ Incomplete JSON detected, requesting completion")
                completion_prompt = "Please complete the JSON response. Return ONLY the complete JSON."
                completion = self.model.invoke(
                    self.messages + [{
                        "role": "user", 
                        "content": [{"type": "text", "text": completion_prompt}]
                    }],
                    max_tokens=4096,
                    temperature=0.7
                )
                response_text = completion.content
            
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
        self.chat = None
        logger.info(f"🤖 Initialized Gemini wrapper with model: {Config.GEMINI_MODEL}")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            # Initialize chat on first call with PDFs
            if self.first_call and self.file_contents:
                logger.info("📄 First call - processing PDFs")
                try:
                    # Start a chat session
                    self.chat = self.model.start_chat()
                    
                    # Send PDFs with initial prompt
                    contents = []
                    for content in self.file_contents:
                        with open(content['file_path'], 'rb') as file:
                            contents.append({
                                "mime_type": "application/pdf",
                                "data": file.read()
                            })
                    
                    # Add text prompt with PDFs
                    contents.append({
                        "text": "Here are the bank statements. Please analyze them."
                    })
                    
                    # Send PDFs to initialize context
                    self.chat.send_message(contents)
                    self.first_call = False
                    logger.info(f"📨 First call - sent {len(contents)-1} PDFs")
                except Exception as e:
                    logger.error(f"Error processing PDFs: {str(e)}")
                    raise
            
            try:
                # Use existing chat or create new one
                if not self.chat:
                    self.chat = self.model.start_chat()
                
                # Send prompt
                response = self.chat.send_message(prompt)
                logger.info("✅ Received response from Gemini")
                
                # Check for incomplete JSON
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
                    raise
                logger.error(f"❌ Error from Gemini: {str(e)}")
                raise

class OpenAIWrapper(LLMWrapper):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.model = Config.OPENAI_MODEL  # "gpt-4-0125-preview"
        self.first_call = True
        self.pdf_content = None
        logger.info(f"🤖 Initialized OpenAI wrapper with model: {self.model}")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            logger.info("➕ Adding new prompt to conversation")
            logger.debug(f"Prompt preview: {str(prompt)[:100]}...")
            
            messages = []
            
            # Process PDFs only on first call
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
                    self.pdf_content = content_text
                    messages.append({
                        "role": "user",
                        "content": f"Here are the bank statements:\n\n{content_text}"
                    })
                    
                self.first_call = False
                logger.info("📨 First call - sent PDFs to OpenAI")
            elif self.pdf_content:
                messages.append({
                    "role": "user",
                    "content": f"Here are the bank statements:\n\n{self.pdf_content}"
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
                    max_tokens=4000,  # Increased token limit
                    presence_penalty=0,
                    frequency_penalty=0
                )
                
                response_text = response.choices[0].message.content
                
                # Check for incomplete JSON
                if response_text.count('{') != response_text.count('}'):
                    logger.warning("⚠️ Incomplete JSON detected, requesting completion")
                    messages.append({
                        "role": "assistant",
                        "content": response_text
                    })
                    messages.append({
                        "role": "user",
                        "content": "Please complete the JSON response. Return ONLY the complete JSON."
                    })
                    
                    completion = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=4000,
                        presence_penalty=0,
                        frequency_penalty=0
                    )
                    response_text = completion.choices[0].message.content
                
                logger.info("✅ OpenAI response received")
                return response_text
                
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
            return GeminiWrapper()
        elif provider == LLMProvider.OPENAI:
            return OpenAIWrapper()
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")