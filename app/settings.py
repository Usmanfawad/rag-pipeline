from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str
    GROQ_API_KEY: str = ""  # Optional - only needed if using Groq models
    PINECONE_API_KEY: str
    
    # Pinecone Configuration
    PINECONE_CLOUD: str = "aws"
    PINECONE_REGION: str = "us-east-1"
    
    # Embedding Configuration
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"  # 1536 dims
    
    # Model Configuration
    DEFAULT_CHAT_MODEL: str = "gpt-4o-mini"
    AVAILABLE_MODELS: str = "gpt-4o-mini,gpt-4o,gpt-3.5-turbo,llama-3.1-8b-instant,llama-3.3-70b-versatile,openai/gpt-oss-120b,openai/gpt-oss-20b"
    
    # Pinecone index names
    INDEX_THERAPY: str = "deidra-therapy"
    INDEX_HEALTH: str = "deidra-health-fitness"
    INDEX_LITERATURE: str = "deidra-literature"
    
    # JWT Configuration
    JWT_SECRET_KEY: str = "your-secret-key-change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 10  # 10 days
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 10  # 10 days

    # Database
    DATABASE_URL: str = "sqlite:///./app.db"


    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()