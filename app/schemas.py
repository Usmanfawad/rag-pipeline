from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any

Domain = Literal["therapy", "health_fitness", "literature"]


# Updated Ingestion Schema (no longer needed for folder ingestion)
class IngestRequest(BaseModel):
    domain: Domain
    data_dir: str = Field(..., description="Directory name under 'data/' folder (e.g., 'therapy')")
    namespace: Optional[str] = Field(None, description="Optional namespace for organization (e.g., 'openai', 'claude')")


class ChatRequest(BaseModel):
    domain: Domain
    question: str = Field(..., description="The question to ask")
    k: int = Field(5, ge=1, le=20, description="Number of documents to retrieve")
    temperature: float = Field(0.2, ge=0.0, le=1.0, description="LLM temperature for response generation")
    model: Optional[str] = Field(None, description="Model to use (OpenAI or Groq). If not specified, uses default model.")


class CompareRequest(BaseModel):
    domain: Domain
    question: str = Field(..., description="The question to ask")
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
    document_name: str  # The name given to this document collection
    user_id: int  # User who uploaded the documents
    results: List[FileProcessingResult]
    errors: Optional[List[FileProcessingError]] = None


class ChatResponse(BaseModel):
    success: bool
    answer: str
    domain: str
    user_id: int  # User who made the request
    parameters: Dict[str, Any]


class ChatDebugResponse(BaseModel):
    success: bool
    answer: str
    context: str
    domain: str
    user_id: int  # User who made the request
    question: str
    raw_docs: List[Dict[str, Any]]
    retrieval_info: Dict[str, Any]


class CompareResponse(BaseModel):
    success: bool
    question: str
    domain: str
    user_id: int  # User who made the request
    with_rag: str
    no_rag: str
    comparison_note: str


class SourcesResponse(BaseModel):
    domain: str
    user_id: int  # User who owns these documents
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


class DocumentDeleteRequest(BaseModel):
    document_ids: List[str] = Field(..., description="List of document IDs to delete from Pinecone")


class DocumentDeleteResponse(BaseModel):
    success: bool
    deleted_count: int
    domain: str
    user_id: int
    deleted_document_ids: List[str]
    message: str


class DocumentInfo(BaseModel):
    id: str
    filename: str
    file_type: str
    chunk_count: int
    metadata: Dict[str, Any]


class DocumentsListResponse(BaseModel):
    success: bool
    domain: str
    user_id: int
    total_documents: int
    total_chunks: int
    documents: List[DocumentInfo]
    message: str