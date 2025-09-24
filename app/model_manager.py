"""
Model Manager for handling multiple LLM providers (OpenAI, Groq)
"""

from typing import Dict, List, Literal, Optional, Union
from enum import Enum
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

from app.settings import settings

# Try to import Groq, but make it optional
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None

class ModelProvider(str, Enum):
    OPENAI = "openai"
    GROQ = "groq"

@dataclass
class ModelInfo:
    name: str
    provider: ModelProvider
    display_name: str
    description: str
    max_tokens: int
    supports_streaming: bool = True
    cost_per_1k_tokens: float = 0.0

# Available models configuration
AVAILABLE_MODELS: Dict[str, ModelInfo] = {
    # OpenAI Models
    "gpt-4o": ModelInfo(
        name="gpt-4o",
        provider=ModelProvider.OPENAI,
        display_name="GPT-4o",
        description="Most capable OpenAI model, best for complex reasoning",
        max_tokens=4096,
        cost_per_1k_tokens=0.03
    ),
    "gpt-4o-mini": ModelInfo(
        name="gpt-4o-mini",
        provider=ModelProvider.OPENAI,
        display_name="GPT-4o Mini",
        description="Fast and efficient OpenAI model, great for most tasks",
        max_tokens=4096,
        cost_per_1k_tokens=0.0015
    ),
    "gpt-3.5-turbo": ModelInfo(
        name="gpt-3.5-turbo",
        provider=ModelProvider.OPENAI,
        display_name="GPT-3.5 Turbo",
        description="Fast and cost-effective OpenAI model",
        max_tokens=4096,
        cost_per_1k_tokens=0.001
    ),
    
    # Groq Models (Based on actual production models)
    "llama-3.1-8b-instant": ModelInfo(
        name="llama-3.1-8b-instant",
        provider=ModelProvider.GROQ,
        display_name="Llama 3.1 8B Instant",
        description="Ultra-fast Llama 3.1 8B model via Groq, instant responses",
        max_tokens=131072,
        cost_per_1k_tokens=0.0
    ),
    "llama-3.3-70b-versatile": ModelInfo(
        name="llama-3.3-70b-versatile",
        provider=ModelProvider.GROQ,
        display_name="Llama 3.3 70B Versatile",
        description="Powerful Llama 3.3 70B model via Groq, excellent for complex reasoning",
        max_tokens=32768,
        cost_per_1k_tokens=0.0
    ),
    "meta-llama/llama-guard-4-12b": ModelInfo(
        name="meta-llama/llama-guard-4-12b",
        provider=ModelProvider.GROQ,
        display_name="Llama Guard 4 12B",
        description="Meta's Llama Guard model for content safety",
        max_tokens=1024,
        cost_per_1k_tokens=0.0
    ),
    "openai/gpt-oss-120b": ModelInfo(
        name="openai/gpt-oss-120b",
        provider=ModelProvider.GROQ,
        display_name="GPT-OSS 120B",
        description="Open source GPT model via Groq",
        max_tokens=65536,
        cost_per_1k_tokens=0.0
    ),
    "openai/gpt-oss-20b": ModelInfo(
        name="openai/gpt-oss-20b",
        provider=ModelProvider.GROQ,
        display_name="GPT-OSS 20B",
        description="Open source GPT model via Groq",
        max_tokens=65536,
        cost_per_1k_tokens=0.0
    ),
    "whisper-large-v3": ModelInfo(
        name="whisper-large-v3",
        provider=ModelProvider.GROQ,
        display_name="Whisper Large v3",
        description="OpenAI's Whisper model for speech recognition via Groq",
        max_tokens=0,  # Audio model
        cost_per_1k_tokens=0.0
    ),
    "whisper-large-v3-turbo": ModelInfo(
        name="whisper-large-v3-turbo",
        provider=ModelProvider.GROQ,
        display_name="Whisper Large v3 Turbo",
        description="Faster OpenAI Whisper model for speech recognition via Groq",
        max_tokens=0,  # Audio model
        cost_per_1k_tokens=0.0
    ),
}

class GroqChatModel(BaseChatModel):
    """Custom wrapper for Groq models to work with LangChain"""
    
    model_name: str
    temperature: float = 0.2
    max_tokens: int = 32768
    
    def __init__(self, model_name: str, api_key: str, temperature: float = 0.2, max_tokens: int = 32768, **kwargs):
        super().__init__(
            model_name=model_name,
            temperature=temperature, 
            max_tokens=max_tokens,
            **kwargs
        )
        if not GROQ_AVAILABLE:
            raise ImportError("Groq library not installed. Install with: uv add groq")
        
        self._client = Groq(api_key=api_key)
    
    class Config:
        arbitrary_types_allowed = True
    
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """Generate response using Groq API"""
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult
        
        # Convert LangChain messages to Groq format
        groq_messages = []
        for msg in messages:
            if hasattr(msg, 'content'):
                role = "user" if msg.__class__.__name__ == "HumanMessage" else "system"
                if msg.__class__.__name__ == "AIMessage":
                    role = "assistant"
                groq_messages.append({"role": role, "content": msg.content})
        
        try:
            response = self._client.chat.completions.create(
                messages=groq_messages,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
            )
            
            content = response.choices[0].message.content
            ai_message = AIMessage(content=content)
            generation = ChatGeneration(message=ai_message)
            
            return ChatResult(generations=[generation])
            
        except Exception as e:
            raise Exception(f"Groq API error: {e}")
    
    def _llm_type(self) -> str:
        return "groq"
    
    @property
    def _identifying_params(self) -> Dict:
        return {"model_name": self.model_name, "temperature": self.temperature}

def get_available_models() -> Dict[str, ModelInfo]:
    """Get all available models based on configured API keys"""
    available = {}
    
    # Always include OpenAI models if API key is available
    if settings.OPENAI_API_KEY:
        for model_id, info in AVAILABLE_MODELS.items():
            if info.provider == ModelProvider.OPENAI:
                available[model_id] = info
    
    # Include Groq models if API key is available and library is installed
    if settings.GROQ_API_KEY and GROQ_AVAILABLE:
        for model_id, info in AVAILABLE_MODELS.items():
            if info.provider == ModelProvider.GROQ:
                available[model_id] = info
    
    return available

def create_chat_model(
    model_name: str, 
    temperature: float = 0.2, 
    max_tokens: Optional[int] = None
) -> BaseChatModel:
    """Create a chat model instance based on the model name"""
    
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(f"Unknown model: {model_name}. Available models: {list(AVAILABLE_MODELS.keys())}")
    
    model_info = AVAILABLE_MODELS[model_name]
    
    if model_info.provider == ModelProvider.OPENAI:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OpenAI API key not configured")
        
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    elif model_info.provider == ModelProvider.GROQ:
        if not settings.GROQ_API_KEY:
            raise ValueError("Groq API key not configured")
        
        if not GROQ_AVAILABLE:
            raise ValueError("Groq library not installed. Install with: uv add groq")
        
        return GroqChatModel(
            model_name=model_name,
            api_key=settings.GROQ_API_KEY,
            temperature=temperature,
            max_tokens=max_tokens or model_info.max_tokens
        )
    
    else:
        raise ValueError(f"Unsupported provider: {model_info.provider}")

def get_model_info(model_name: str) -> Optional[ModelInfo]:
    """Get information about a specific model"""
    return AVAILABLE_MODELS.get(model_name)

def get_models_by_provider(provider: ModelProvider) -> Dict[str, ModelInfo]:
    """Get all models for a specific provider"""
    return {
        model_id: info 
        for model_id, info in AVAILABLE_MODELS.items() 
        if info.provider == provider
    }

def validate_model_access(model_name: str) -> tuple[bool, str]:
    """Validate if a model can be accessed with current configuration"""
    if model_name not in AVAILABLE_MODELS:
        return False, f"Unknown model: {model_name}"
    
    model_info = AVAILABLE_MODELS[model_name]
    
    if model_info.provider == ModelProvider.OPENAI:
        if not settings.OPENAI_API_KEY:
            return False, "OpenAI API key not configured"
    
    elif model_info.provider == ModelProvider.GROQ:
        if not settings.GROQ_API_KEY:
            return False, "Groq API key not configured"
        if not GROQ_AVAILABLE:
            return False, "Groq library not installed"
    
    return True, "Model accessible"

# Namespace suggestions based on model choice
def suggest_namespace_for_model(model_name: str) -> str:
    """Suggest a namespace based on the model being used"""
    if model_name not in AVAILABLE_MODELS:
        return "default"
    
    model_info = AVAILABLE_MODELS[model_name]
    
    if model_info.provider == ModelProvider.OPENAI:
        return f"openai-{model_name.replace('.', '-')}"
    elif model_info.provider == ModelProvider.GROQ:
        return f"groq-{model_name.replace('.', '-')}"
    
    return "default"
