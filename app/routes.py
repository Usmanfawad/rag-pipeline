from pathlib import Path
from typing import List
import asyncio

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse

from app.schemas import IngestRequest, ChatRequest, CompareRequest, FileUploadResponse
from app.ingestion import ingest_folder, ingest_uploaded_file
from app.rag_chain import build_rag_chain, get_available_sources
from app.model_manager import get_available_models, get_model_info, validate_model_access, suggest_namespace_for_model
from app.settings import settings

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
async def upload_files(
    domain: str = Form(...),
    namespace: str = Form(None),
    files: List[UploadFile] = File(...)
):
    """Upload and ingest multiple files."""
    if domain not in ["therapy", "health_fitness", "literature"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid domain. Must be one of: therapy, health_fitness, literature"
        )
    
    results = []
    total_chunks = 0
    errors = []
    
    for file in files:
        try:
            # Check file extension
            file_path = Path(file.filename)
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                errors.append({
                    "filename": file.filename,
                    "error": f"Unsupported file type: {file_path.suffix}",
                    "supported_types": sorted(list(SUPPORTED_EXTENSIONS))
                })
                continue
            
            # Read file content
            content = await file.read()
            if not content:
                errors.append({
                    "filename": file.filename,
                    "error": "File is empty"
                })
                continue
            
            # Ingest the file
            chunks = await ingest_uploaded_file(
                domain=domain,
                file_content=content,
                filename=file.filename,
                namespace=namespace
            )
            
            results.append({
                "filename": file.filename,
                "chunks_indexed": chunks,
                "file_size": len(content),
                "file_type": file_path.suffix.lower(),
                "status": "success"
            })
            total_chunks += chunks
            
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    return FileUploadResponse(
        success=len(errors) == 0,
        total_files_processed=len(files),
        successful_files=len(results),
        total_chunks_indexed=total_chunks,
        domain=domain,
        namespace=namespace,
        results=results,
        errors=errors if errors else None
    )


@router.post("/chat")
def chat(req: ChatRequest):
    """Chat with the RAG system."""
    try:
        # Validate model if specified
        if req.model:
            is_accessible, access_message = validate_model_access(req.model)
            if not is_accessible:
                raise HTTPException(status_code=400, detail=f"Model not accessible: {access_message}")
        
        chain = build_rag_chain(
            domain=req.domain,
            namespace=req.namespace,
            k=req.k,
            temperature=req.temperature,
            model=req.model
        )
        answer = chain.invoke(req.question)
        
        # Get model info for response
        model_used = req.model or settings.DEFAULT_CHAT_MODEL
        model_info = get_model_info(model_used)
        
        return {
            "success": True,
            "answer": answer,
            "domain": req.domain,
            "namespace": req.namespace,
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
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/debug")
def chat_debug(req: ChatRequest):
    """Chat with debug information showing retrieved context."""
    try:
        # Validate model if specified
        if req.model:
            is_accessible, access_message = validate_model_access(req.model)
            if not is_accessible:
                raise HTTPException(status_code=400, detail=f"Model not accessible: {access_message}")
        
        chain = build_rag_chain(
            domain=req.domain,
            namespace=req.namespace,
            k=req.k,
            temperature=req.temperature,
            model=req.model,
            peek_context=True
        )
        result = chain.invoke(req.question)
        
        return {
            "success": True,
            "domain": req.domain,
            "namespace": req.namespace,
            "question": req.question,
            **result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
def compare(req: CompareRequest):
    """Compare RAG vs non-RAG responses."""
    try:
        # Validate model if specified
        if req.model:
            is_accessible, access_message = validate_model_access(req.model)
            if not is_accessible:
                raise HTTPException(status_code=400, detail=f"Model not accessible: {access_message}")
        
        model_to_use = req.model or settings.DEFAULT_CHAT_MODEL
        
        # RAG response
        chain = build_rag_chain(
            req.domain, 
            namespace=req.namespace, 
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

        return {
            "success": True,
            "question": req.question,
            "domain": req.domain,
            "namespace": req.namespace,
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources/{domain}")
def get_sources(domain: str, namespace: str = None):
    """Get information about available sources in a domain."""
    if domain not in ["therapy", "health_fitness", "literature"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid domain. Must be one of: therapy, health_fitness, literature"
        )
    
    try:
        sources_info = get_available_sources(domain, namespace)
        return sources_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear/{domain}")
def clear_domain(domain: str, namespace: str = None):
    """Clear all data from a domain (use with caution)."""
    if domain not in ["therapy", "health_fitness", "literature"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid domain. Must be one of: therapy, health_fitness, literature"
        )
    
    try:
        from pinecone import Pinecone
        from app.ingestion import _index_name
        
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        index = pc.Index(_index_name(domain))
        
        # Delete all vectors in the namespace
        if namespace:
            index.delete(delete_all=True, namespace=namespace)
            message = f"Cleared all data from domain '{domain}', namespace '{namespace}'"
        else:
            # Clear default namespace
            index.delete(delete_all=True, namespace="")
            message = f"Cleared all data from domain '{domain}' (default namespace)"
        
        return {
            "success": True,
            "message": message,
            "domain": domain,
            "namespace": namespace
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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