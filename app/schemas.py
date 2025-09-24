from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

Domain = Literal["therapy", "health_fitness", "literature"]


class IngestRequest(BaseModel):
    domain: Domain
    data_dir: str = Field(..., description="Directory name under 'data/' folder (e.g., 'therapy')")
    namespace: Optional[str] = Field(None, description="Optional namespace for organization (e.g., 'openai', 'claude')")


class ChatRequest(BaseModel):
    domain: Domain
    question: str = Field(..., description="The question to ask")
    namespace: Optional[str] = Field(None, description="Optional namespace to search in")
    k: int = Field(5, ge=1, le=20, description="Number of documents to retrieve")
    temperature: float = Field(0.2, ge=0.0, le=1.0, description="LLM temperature for response generation")
    model: Optional[str] = Field(None, description="Model to use (OpenAI or Groq). If not specified, uses default model.")


class CompareRequest(BaseModel):
    domain: Domain
    question: str = Field(..., description="The question to ask")
    namespace: Optional[str] = Field(None, description="Optional namespace to search in")
    k: int = Field(5, ge=1, le=20, description="Number of documents to retrieve for RAG")
    temperature: float = Field(0.2, ge=0.0, le=1.0, description="LLM temperature for response generation")
    model: Optional[str] = Field(None, description="Model to use for RAG response")


class FileProcessingResult(BaseModel):
    filename: str
    chunks_indexed: int
    file_size: int
    file_type: str
    status: str


class FileProcessingError(BaseModel):
    filename: str
    error: str
    supported_types: Optional[List[str]] = None


class FileUploadResponse(BaseModel):
    success: bool
    total_files_processed: int
    successful_files: int
    total_chunks_indexed: int
    domain: str
    namespace: Optional[str]
    results: List[FileProcessingResult]
    errors: Optional[List[FileProcessingError]] = None


class ChatResponse(BaseModel):
    success: bool
    answer: str
    domain: str
    namespace: Optional[str]
    parameters: Dict[str, Any]


class ChatDebugResponse(BaseModel):
    success: bool
    answer: str
    context: str
    domain: str
    namespace: Optional[str]
    question: str
    raw_docs: List[Dict[str, Any]]
    retrieval_info: Dict[str, Any]


class CompareResponse(BaseModel):
    success: bool
    question: str
    domain: str
    namespace: Optional[str]
    with_rag: str
    no_rag: str
    comparison_note: str


class SourcesResponse(BaseModel):
    domain: str
    namespace: Optional[str]
    total_chunks_sampled: int
    unique_sources: int
    sources: List[str]
    file_types: List[str]
    status: str


class SystemStats(BaseModel):
    success: bool
    domains: Dict[str, Dict[str, Any]]
    supported_formats: int
    system_status: str