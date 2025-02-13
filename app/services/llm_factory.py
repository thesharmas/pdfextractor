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
from app.services.rate_limiter import RATE_LIMITERS
from app.services.token_tracker import token_tracker

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
        self.rate_limiter = RATE_LIMITERS["claude"]
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
            
            message_content.append({
                "type": "text",
                "text": prompt
            })
            
            self.messages.append({
                "role": "user",
                "content": message_content
            })
            
        try:
            estimated_tokens = len(str(self.messages)) * 1.3
            self.rate_limiter.check_limits(int(estimated_tokens))
            
            result = self.model.invoke(
                self.messages,
                max_tokens=4096,
                temperature=0.7
            )
            
            # Track token usage
            token_tracker.track_usage(
                input_text=str(self.messages),
                output_text=result.content,
                model=Config.CLAUDE_MODEL,
                endpoint="messages"
            )
            
            self.messages.append({
                "role": "assistant",
                "content": result.content
            })
            
            response_text = result.content
            if response_text.count('{') != response_text.count('}'):
                logger.warning("⚠️ Incomplete JSON detected, requesting completion")
                completion_prompt = "Please complete the JSON response. Return ONLY the complete JSON."
                
                self.rate_limiter.check_limits(1000)
                
                completion = self.model.invoke(
                    self.messages + [{
                        "role": "user", 
                        "content": [{"type": "text", "text": completion_prompt}]
                    }],
                    max_tokens=4096,
                    temperature=0.7
                )
                
                # Track completion request tokens
                token_tracker.track_usage(
                    input_text=completion_prompt,
                    output_text=completion.content,
                    model=Config.CLAUDE_MODEL,
                    endpoint="messages/completion"
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
        self.rate_limiter = RATE_LIMITERS["gemini"]
        logger.info(f"🤖 Initialized Gemini wrapper with model: {Config.GEMINI_MODEL}")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            if self.first_call and self.file_contents:
                logger.info("📄 First call - processing PDFs")
                try:
                    self.chat = self.model.start_chat()
                    
                    contents = []
                    for content in self.file_contents:
                        with open(content['file_path'], 'rb') as file:
                            contents.append({
                                "mime_type": "application/pdf",
                                "data": file.read()
                            })
                    
                    contents.append({
                        "text": "Here are the bank statements. Please analyze them."
                    })
                    
                    self.rate_limiter.check_limits(2000)
                    self.chat.send_message(contents)
                    
                    # Track PDF processing request
                    token_tracker.track_usage(
                        input_text=str(contents),
                        output_text="",
                        model=Config.GEMINI_MODEL,
                        endpoint="start_chat"
                    )
                    
                    self.first_call = False
                    
                except Exception as e:
                    logger.error(f"Error processing PDFs: {str(e)}")
                    raise
            
            try:
                if not self.chat:
                    self.chat = self.model.start_chat()
                
                estimated_tokens = len(prompt) * 1.3
                self.rate_limiter.check_limits(int(estimated_tokens))
                
                response = self.chat.send_message(prompt)
                
                # Track main request
                token_tracker.track_usage(
                    input_text=prompt,
                    output_text=response.text,
                    model=Config.GEMINI_MODEL,
                    endpoint="send_message"
                )
                
                logger.info("✅ Received response from Gemini")
                
                response_text = response.text
                if response_text.count('{') != response_text.count('}'):
                    logger.warning("⚠️ Incomplete JSON detected, requesting completion")
                    
                    self.rate_limiter.check_limits(1000)
                    
                    completion = self.chat.send_message(
                        "Please complete the JSON response. Return ONLY the complete JSON."
                    )
                    
                    # Track completion request
                    token_tracker.track_usage(
                        input_text="Please complete the JSON response",
                        output_text=completion.text,
                        model=Config.GEMINI_MODEL,
                        endpoint="send_message/completion"
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
        self.model = Config.OPENAI_MODEL
        self.first_call = True
        self.pdf_content = None
        self.rate_limiter = RATE_LIMITERS["openai"]
        logger.info(f"🤖 Initialized OpenAI wrapper with model: {self.model}")

    def get_response(self, prompt: str = None) -> str:
        if prompt:
            logger.info("➕ Adding new prompt to conversation")
            logger.debug(f"Prompt preview: {str(prompt)[:100]}...")
            
            messages = []
            
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
            
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            try:
                logger.info(f"📨 Sending to OpenAI with {len(messages)} messages")
                
                estimated_tokens = len(str(messages)) * 1.3
                self.rate_limiter.check_limits(int(estimated_tokens))
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=4000,
                    presence_penalty=0,
                    frequency_penalty=0
                )
                
                # Track main request
                token_tracker.track_usage(
                    input_text=str(messages),
                    output_text=response.choices[0].message.content,
                    model=Config.OPENAI_MODEL,
                    endpoint="chat/completions"
                )
                
                response_text = response.choices[0].message.content
                
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
                    
                    self.rate_limiter.check_limits(1000)
                    
                    completion = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=4000,
                        presence_penalty=0,
                        frequency_penalty=0
                    )
                    
                    # Track completion request
                    token_tracker.track_usage(
                        input_text=str(messages[-2:]),
                        output_text=completion.choices[0].message.content,
                        model=Config.OPENAI_MODEL,
                        endpoint="chat/completions/completion"
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