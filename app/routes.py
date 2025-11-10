from pathlib import Path
from typing import List
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends

from app.schemas import IngestRequest, ChatRequest, CompareRequest, FileUploadResponse, DocumentDeleteRequest, DocumentDeleteResponse, DocumentsListResponse, DocumentInfo
from app.auth import User, get_current_active_user, get_user_namespace
from app.ingestion import ingest_folder, ingest_uploaded_file
from app.rag_chain import build_rag_chain, get_available_sources
from app.model_manager import get_available_models, get_model_info, validate_model_access, suggest_namespace_for_model
from app.settings import settings
from app.log import app_logger

router = APIRouter()

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    # Documents
    '.pdf', '.docx', '.doc', '.pptx', '.ppt', '.rtf',
    # Text formats
    '.txt', '.md', '.markdown', '.html', '.htm', '.xml',
    # Data formats
    '.csv', '.xlsx', '.xls', '.json',
    # Code files
    '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c', '.cs',
    '.go', '.php', '.rb', '.rs', '.scala', '.swift', '.kt', '.r',
    '.sql', '.css', '.scss', '.less'
}

@router.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "message": "RAG Pipeline is running"}


@router.get("/get_user", response_model=User)
async def get_user(current_user: User = Depends(get_current_active_user)):
    """
    Get user information by JWT token.
    
    Returns detailed user information including id, email, full_name, 
    is_active status, and timestamps for the authenticated user.
    Accepts JWT token in Authorization header.
    """
    return current_user


@router.get("/supported-formats")
def get_supported_formats():
    """Get list of supported file formats."""
    return {
        "supported_extensions": sorted(list(SUPPORTED_EXTENSIONS)),
        "categories": {
            "documents": [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".rtf"],
            "text_formats": [".txt", ".md", ".markdown", ".html", ".htm", ".xml"],
            "data_formats": [".csv", ".xlsx", ".xls", ".json"],
            "code_files": [".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cpp", 
                          ".c", ".cs", ".go", ".php", ".rb", ".rs", ".scala", 
                          ".swift", ".kt", ".r", ".sql", ".css", ".scss", ".less"]
        },
        "total_supported": len(SUPPORTED_EXTENSIONS)
    }


@router.get("/models")
def get_models():
    """Get list of available models."""
    try:
        available_models = get_available_models()
        
        models_by_provider = {}
        for model_id, model_info in available_models.items():
            provider = model_info.provider.value
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            
            models_by_provider[provider].append({
                "id": model_id,
                "name": model_info.display_name,
                "description": model_info.description,
                "max_tokens": model_info.max_tokens,
                "cost_per_1k_tokens": model_info.cost_per_1k_tokens
            })
        
        return {
            "success": True,
            "total_models": len(available_models),
            "providers": models_by_provider,
            "default_model": settings.DEFAULT_CHAT_MODEL
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/models")
def get_chat_models():
    """Get list of available LLM models for chat functionality."""
    try:
        available_models = get_available_models()
        
        # Filter out non-chat models (like Whisper audio models)
        chat_models = {
            model_id: model_info 
            for model_id, model_info in available_models.items()
            if model_info.max_tokens > 0  # Audio models have max_tokens=0
        }
        
        models_by_provider = {}
        for model_id, model_info in chat_models.items():
            provider = model_info.provider.value
            if provider not in models_by_provider:
                models_by_provider[provider] = []
            
            models_by_provider[provider].append({
                "id": model_id,
                "name": model_info.display_name,
                "description": model_info.description,
                "max_tokens": model_info.max_tokens,
                "supports_streaming": model_info.supports_streaming,
                "cost_per_1k_tokens": model_info.cost_per_1k_tokens
            })
        
        return {
            "success": True,
            "total_models": len(chat_models),
            "providers": models_by_provider,
            "default_model": settings.DEFAULT_CHAT_MODEL,
            "message": "These models can be used with the /chat endpoint"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_name}")
def get_model_details(model_name: str):
    """Get details about a specific model."""
    try:
        model_info = get_model_info(model_name)
        if not model_info:
            raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
        
        is_accessible, access_message = validate_model_access(model_name)
        suggested_namespace = suggest_namespace_for_model(model_name)
        
        return {
            "success": True,
            "model": {
                "id": model_name,
                "name": model_info.display_name,
                "provider": model_info.provider.value,
                "description": model_info.description,
                "max_tokens": model_info.max_tokens,
                "supports_streaming": model_info.supports_streaming,
                "cost_per_1k_tokens": model_info.cost_per_1k_tokens
            },
            "accessibility": {
                "accessible": is_accessible,
                "message": access_message
            },
            "suggested_namespace": suggested_namespace
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
def ingest_folder_endpoint(req: IngestRequest):
    """Ingest all supported files from a folder."""
    try:
        data_path = Path("data") / req.data_dir
        if not data_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Data directory not found: {data_path}"
            )
        
        n = ingest_folder(req.domain, data_path, namespace=req.namespace)
        
        return {
            "success": True,
            "indexed_chunks": n,
            "domain": req.domain,
            "namespace": req.namespace,
            "data_directory": str(data_path),
            "message": f"Successfully indexed {n} chunks"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    domain: str = Form(...),
    document_name: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    user_namespace: str = Depends(get_user_namespace)
):
    """Upload and ingest a single file for the authenticated user."""
    if domain not in ["therapy", "health_fitness", "literature"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid domain. Must be one of: therapy, health_fitness, literature"
        )
    
    app_logger.info(f"User {current_user.email} (ID: {current_user.id}) uploading file '{file.filename}' to domain '{domain}' with document name '{document_name}'")
    
    try:
        # Check file extension
        file_path = Path(file.filename)
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_path.suffix}. Supported types: {sorted(list(SUPPORTED_EXTENSIONS))}"
            )
        
        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(
                status_code=400,
                detail="File is empty"
            )
        
        # Create enhanced metadata for ingestion
        enhanced_metadata = {
            "user_id": current_user.id,
            "user_email": current_user.email,
            "document_name": document_name,
            "domain": domain,
            "upload_date": datetime.utcnow().isoformat(),
            "file_size": len(content)
        }
        
        # Ingest the file with user-specific namespace and enhanced metadata
        chunks = await ingest_uploaded_file(
            domain=domain,
            file_content=content,
            filename=file.filename,
            namespace=user_namespace,
            metadata=enhanced_metadata
        )
        
        result = {
            "filename": file.filename,
            "chunks_indexed": chunks,
            "file_size": len(content),
            "file_type": file_path.suffix.lower(),
            "status": "success"
        }
        
        app_logger.info(f"Upload completed for user {current_user.id}: {file.filename} -> {chunks} chunks")
        
        return FileUploadResponse(
            success=True,
            total_files_processed=1,
            successful_files=1,
            total_chunks_indexed=chunks,
            domain=domain,
            document_name=document_name,
            user_id=current_user.id,
            results=[result],
            errors=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Error processing file {file.filename} for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file: {str(e)}"
        )


@router.post("/chat")
def chat(
    req: ChatRequest, 
    current_user: User = Depends(get_current_active_user),
    user_namespace: str = Depends(get_user_namespace)
):
    """Chat with the RAG system using user's documents."""
    try:
        # Validate model if specified
        if req.model:
            is_accessible, access_message = validate_model_access(req.model)
            if not is_accessible:
                raise HTTPException(status_code=400, detail=f"Model not accessible: {access_message}")
        
        app_logger.info(f"User {current_user.email} (ID: {current_user.id}) asking question in domain '{req.domain}'")
        
        chain = build_rag_chain(
            domain=req.domain,
            namespace=user_namespace,
            k=req.k,
            temperature=req.temperature,
            model=req.model
        )
        answer = chain.invoke(req.question)
        
        # Get model info for response
        model_used = req.model or settings.DEFAULT_CHAT_MODEL
        model_info = get_model_info(model_used)
        
        app_logger.info(f"Chat completed for user {current_user.id} in domain '{req.domain}'")
        
        return {
            "success": True,
            "answer": answer,
            "domain": req.domain,
            "user_id": current_user.id,
            "model_used": {
                "name": model_used,
                "display_name": model_info.display_name if model_info else model_used,
                "provider": model_info.provider.value if model_info else "unknown"
            },
            "parameters": {
                "k": req.k,
                "temperature": req.temperature,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Chat error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/debug")
def chat_debug(
    req: ChatRequest, 
    current_user: User = Depends(get_current_active_user),
    user_namespace: str = Depends(get_user_namespace)
):
    """Chat with debug information showing retrieved context."""
    try:
        # Validate model if specified
        if req.model:
            is_accessible, access_message = validate_model_access(req.model)
            if not is_accessible:
                raise HTTPException(status_code=400, detail=f"Model not accessible: {access_message}")
        
        app_logger.info(f"User {current_user.email} (ID: {current_user.id}) using debug chat in domain '{req.domain}'")
        
        chain = build_rag_chain(
            domain=req.domain,
            namespace=user_namespace,
            k=req.k,
            temperature=req.temperature,
            model=req.model,
            peek_context=True
        )
        result = chain.invoke(req.question)
        
        return {
            "success": True,
            "domain": req.domain,
            "user_id": current_user.id,
            "question": req.question,
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Debug chat error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
def compare(
    req: CompareRequest, 
    current_user: User = Depends(get_current_active_user),
    user_namespace: str = Depends(get_user_namespace)
):
    """Compare RAG vs non-RAG responses using user's documents."""
    try:
        # Validate model if specified
        if req.model:
            is_accessible, access_message = validate_model_access(req.model)
            if not is_accessible:
                raise HTTPException(status_code=400, detail=f"Model not accessible: {access_message}")
        
        model_to_use = req.model or settings.DEFAULT_CHAT_MODEL
        
        app_logger.info(f"User {current_user.email} (ID: {current_user.id}) using compare in domain '{req.domain}'")
        
        # RAG response using user's documents
        chain = build_rag_chain(
            req.domain, 
            namespace=user_namespace, 
            k=req.k,
            temperature=req.temperature,
            model=model_to_use
        )
        with_rag = chain.invoke(req.question)

        # Non-RAG response using the same model
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        direct_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant. Answer based on your general knowledge. If unsure about specific details, acknowledge your uncertainty."),
            ("human", "{q}")
        ])
        
        # Use the same model for fair comparison
        try:
            from app.model_manager import create_chat_model
            llm = create_chat_model(model_to_use, temperature=req.temperature)
        except:
            # Fallback to OpenAI
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                api_key=settings.OPENAI_API_KEY, 
                model=settings.DEFAULT_CHAT_MODEL,
                temperature=req.temperature
            )
        
        direct_chain = direct_prompt | llm | StrOutputParser()
        no_rag = direct_chain.invoke({"q": req.question})

        # Get model info
        model_info = get_model_info(model_to_use)

        app_logger.info(f"Compare completed for user {current_user.id} in domain '{req.domain}'")

        return {
            "success": True,
            "question": req.question,
            "domain": req.domain,
            "user_id": current_user.id,
            "model_used": {
                "name": model_to_use,
                "display_name": model_info.display_name if model_info else model_to_use,
                "provider": model_info.provider.value if model_info else "unknown"
            },
            "with_rag": with_rag,
            "no_rag": no_rag,
            "comparison_note": "The 'with_rag' response uses your uploaded documents, while 'no_rag' uses only the model's general knowledge. Both use the same model for fair comparison."
        }
    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Compare error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources/{domain}")
def get_sources(
    domain: str, 
    current_user: User = Depends(get_current_active_user),
    user_namespace: str = Depends(get_user_namespace)
):
    """Get information about available sources in a domain for the authenticated user."""
    if domain not in ["therapy", "health_fitness", "literature"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid domain. Must be one of: therapy, health_fitness, literature"
        )
    
    try:
        
        app_logger.info(f"User {current_user.email} (ID: {current_user.id}) requesting sources for domain '{domain}'")
        
        sources_info = get_available_sources(domain, user_namespace)
        
        # Update response to include user_id
        if isinstance(sources_info, dict):
            sources_info["user_id"] = current_user.id
        
        return sources_info
    except Exception as e:
        app_logger.error(f"Sources error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear/{domain}")
def clear_domain(
    domain: str, 
    current_user: User = Depends(get_current_active_user),
    user_namespace: str = Depends(get_user_namespace)
):
    """Clear all data from a domain for the authenticated user (use with caution)."""
    if domain not in ["therapy", "health_fitness", "literature"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid domain. Must be one of: therapy, health_fitness, literature"
        )
    
    try:
        from pinecone import Pinecone
        from app.ingestion import _index_name
        
        app_logger.warning(f"User {current_user.email} (ID: {current_user.id}) clearing all data from domain '{domain}'")
        
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index = pc.Index(_index_name(domain))
        
        # Delete all vectors in the user's namespace
        index.delete(delete_all=True, namespace=user_namespace)
        
        message = f"Cleared all data from domain '{domain}' for user {current_user.email}"
        
        app_logger.info(f"Data cleared successfully for user {current_user.id} in domain '{domain}'")
        
        return {
            "success": True,
            "message": message,
            "domain": domain,
            "user_id": current_user.id
        }
    except Exception as e:
        app_logger.error(f"Clear domain error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{domain}", response_model=DocumentsListResponse)
def get_user_documents(
    domain: str,
    current_user: User = Depends(get_current_active_user),
    user_namespace: str = Depends(get_user_namespace)
):
    """Get all documents for the authenticated user in a specific domain."""
    if domain not in ["therapy", "health_fitness", "literature"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid domain. Must be one of: therapy, health_fitness, literature"
        )
    
    try:
        from pinecone import Pinecone
        from app.ingestion import _index_name
        from collections import defaultdict
        
        app_logger.info(
            f"User {current_user.email} (ID: {current_user.id}) requesting documents from domain '{domain}'"
        )
        
        # Connect to Pinecone
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index = pc.Index(_index_name(domain))
        
        # Query all vectors in the user's namespace
        # We'll use a dummy query to get all vectors
        dummy_query = [0.0] * 1536  # OpenAI embedding dimension
        
        # Query with high limit to get all vectors
        query_response = index.query(
            vector=dummy_query,
            top_k=10000,  # High limit to get all documents
            namespace=user_namespace,
            include_metadata=True
        )
        
        # Group chunks by document ID
        document_chunks = defaultdict(list)
        total_chunks = 0
        
        for match in query_response.matches:
            metadata = match.metadata or {}
            doc_id = metadata.get('document_id', 'unknown')
            
            document_chunks[doc_id].append({
                'chunk_id': match.id,
                'metadata': metadata
            })
            total_chunks += 1
        
        # Create document info
        documents = []
        for doc_id, chunks in document_chunks.items():
            # Get metadata from first chunk (should be consistent across chunks)
            first_chunk_metadata = chunks[0]['metadata']
            
            documents.append(DocumentInfo(
                id=doc_id,
                filename=first_chunk_metadata.get('filename', 'Unknown'),
                file_type=first_chunk_metadata.get('file_type', 'Unknown'),
                chunk_count=len(chunks),
                metadata={
                    'upload_date': first_chunk_metadata.get('upload_date'),
                    'file_size': first_chunk_metadata.get('file_size'),
                    'source': first_chunk_metadata.get('source', 'uploaded'),
                    'user_id': first_chunk_metadata.get('user_id'),
                    'user_email': first_chunk_metadata.get('user_email'),
                    'document_name': first_chunk_metadata.get('document_name'),
                    'domain': first_chunk_metadata.get('domain'),
                    'ingestion_timestamp': first_chunk_metadata.get('ingestion_timestamp')
                }
            ))
        
        # Sort documents by filename
        documents.sort(key=lambda x: x.filename)
        
        app_logger.info(
            f"Found {len(documents)} documents with {total_chunks} total chunks for user {current_user.id} in domain '{domain}'"
        )
        
        return DocumentsListResponse(
            success=True,
            domain=domain,
            user_id=current_user.id,
            total_documents=len(documents),
            total_chunks=total_chunks,
            documents=documents,
            message=f"Found {len(documents)} document(s) with {total_chunks} total chunk(s)"
        )
        
    except Exception as e:
        app_logger.error(f"Get documents error for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve documents: {str(e)}"
        )


@router.delete("/documents", response_model=DocumentDeleteResponse)
def delete_documents(
    delete_request: DocumentDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    user_namespace: str = Depends(get_user_namespace)
):
    """Delete specific documents from the user's namespace in Pinecone across all domains."""
    if not delete_request.document_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one document ID must be provided"
        )
    
    try:
        from pinecone import Pinecone
        from app.ingestion import _index_name
        
        app_logger.info(
            f"User {current_user.email} (ID: {current_user.id}) deleting {len(delete_request.document_ids)} documents: {delete_request.document_ids}"
        )
        
        # Connect to Pinecone
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        
        # Delete from all domains (since document IDs are unique)
        domains = ["therapy", "health_fitness", "literature"]
        total_deleted = 0
        
        for domain in domains:
            try:
                index = pc.Index(_index_name(domain))
                # Delete documents from user's namespace in this domain
                index.delete(ids=delete_request.document_ids, namespace=user_namespace)
                total_deleted += len(delete_request.document_ids)
            except Exception as e:
                app_logger.warning(f"Could not delete from domain {domain}: {str(e)}")
                # Continue with other domains
        
        app_logger.info(
            f"Successfully deleted {total_deleted} document references for user {current_user.id}"
        )
        
        return DocumentDeleteResponse(
            success=True,
            deleted_count=total_deleted,
            domain="all",  # Since we deleted from all domains
            user_id=current_user.id,
            deleted_document_ids=delete_request.document_ids,
            message=f"Successfully deleted {total_deleted} document reference(s) across all domains"
        )
        
    except Exception as e:
        app_logger.error(f"Delete documents error for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to delete documents: {str(e)}"
        )


@router.get("/stats")
def get_system_stats():
    """Get system statistics."""
    try:
        stats = {}
        
        for domain in ["therapy", "health_fitness", "literature"]:
            try:
                sources_info = get_available_sources(domain)
                stats[domain] = {
                    "status": sources_info.get("status", "unknown"),
                    "total_chunks": sources_info.get("total_chunks_sampled", 0),
                    "unique_sources": sources_info.get("unique_sources", 0),
                    "file_types": sources_info.get("file_types", [])
                }
            except Exception as e:
                stats[domain] = {"status": "error", "error": str(e)}
        
        return {
            "success": True,
            "domains": stats,
            "supported_formats": len(SUPPORTED_EXTENSIONS),
            "system_status": "operational"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))