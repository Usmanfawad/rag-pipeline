from typing import Literal, Optional, List, Dict, Any
import re

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.documents import Document

from app.settings import settings
from app.model_manager import create_chat_model, get_model_info, suggest_namespace_for_model

Domain = Literal["therapy", "health_fitness", "literature"]

# Enhanced system prompt for better context understanding
SYSTEM = """You are a precise and knowledgeable assistant specialized in analyzing user-uploaded documents and data.

INSTRUCTIONS:
- Use the provided CONTEXT to answer the QUESTION accurately and comprehensively
- The context contains documents uploaded by the user, organized by domain and document collections
- If the context contains partial information, provide what you can and clearly state what information is missing
- If no relevant information is found, clearly state that you don't have sufficient information in the user's uploaded documents
- Do not ask the user to provide more information or context
- Always cite your sources using the format: (source: <document name or filename>)
- When dealing with structured data (CSV/Excel), interpret the data meaningfully
- For technical documents, explain concepts clearly while maintaining accuracy
- Preserve important details like statistics, dates, names, and specific findings
- Be aware that the information comes from the user's personal document collection

RESPONSE GUIDELINES:
- Be comprehensive but concise
- Use bullet points or numbered lists when presenting multiple items
- Highlight key findings or important information
- If data contains numbers or statistics, present them clearly
- Maintain professional tone appropriate for the domain
- Acknowledge when information comes from the user's specific document collection
"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", "CONTEXT:\n{context}\n\nQUESTION: {question}")
    ]
)

def _index_name(domain: Domain) -> str:
    if domain == "therapy":
        return settings.INDEX_THERAPY
    if domain == "health_fitness":
        return settings.INDEX_HEALTH
    return settings.INDEX_LITERATURE


def _format_context(docs: List[Document]) -> str:
    """Format retrieved documents into a coherent context string."""
    if not docs:
        return "No relevant information found in the dataset."
    
    parts = []
    seen_sources = set()
    
    for i, d in enumerate(docs, 1):
        # Extract source information
        source = d.metadata.get("source", "Unknown source")
        filetype = d.metadata.get("filetype") or d.metadata.get("file_type", "")
        page = d.metadata.get("page")
        sheet = d.metadata.get("sheet")
        slide = d.metadata.get("slide")
        
        # Extract additional metadata for better context
        filename = d.metadata.get("filename", source)
        document_name = d.metadata.get("document_name")
        domain = d.metadata.get("domain")
        
        # Create source identifier with better context
        source_id = filename if filename != "Unknown source" else source
        if document_name and document_name != filename:
            source_id = f"{document_name} ({filename})"
        
        # Add page/sheet/slide information
        if page is not None:
            source_id += f", page {page}"
        elif sheet:
            source_id += f", sheet '{sheet}'"
        elif slide is not None:
            source_id += f", slide {slide}"
        
        # Format content with metadata context
        content = d.page_content.strip()
        
        # Add file type context for better understanding
        if filetype in ["csv", "excel"]:
            content_header = f"[Structured Data from {filetype.upper()}]"
        elif filetype == "code":
            lang = d.metadata.get("language", "unknown")
            content_header = f"[Code - {lang.upper()}]"
        elif filetype in ["pdf", "docx", "pptx"]:
            content_header = f"[Document - {filetype.upper()}]"
        else:
            content_header = f"[{filetype.upper() if filetype else 'Text'}]"
        
        formatted_content = f"{content_header}\n{content}\n(source: {source_id})"
        parts.append(formatted_content)
        seen_sources.add(source)
    
    context = "\n\n---\n\n".join(parts)
    
    # Add summary of sources at the end
    if len(seen_sources) > 1:
        context += f"\n\n[Note: Information retrieved from {len(seen_sources)} sources: {', '.join(sorted(seen_sources))}]"
    
    return context


def _preprocess_query(query: str) -> str:
    """Preprocess query to improve retrieval quality."""
    # Remove extra whitespace
    query = re.sub(r'\s+', ' ', query.strip())
    
    # Expand common abbreviations that might be in documents
    abbreviations = {
        "ptsd": "post-traumatic stress disorder PTSD",
        "adhd": "attention deficit hyperactivity disorder ADHD",
        "ai": "artificial intelligence AI",
        "ml": "machine learning ML",
        "api": "application programming interface API",
        "ui": "user interface UI",
        "ux": "user experience UX",
        "db": "database DB",
        "sql": "structured query language SQL",
    }
    
    query_lower = query.lower()
    for abbr, expansion in abbreviations.items():
        if abbr in query_lower:
            query = query + f" {expansion}"
    
    return query


def _query_rewriter():
    """Get a small, fast model for query rewriting."""
    try:
        # Try to use the fastest available model for query rewriting
        return create_chat_model("gpt-4o-mini", temperature=0.0)
    except:
        # Fallback to default OpenAI model
        return ChatOpenAI(
            api_key=settings.OPENAI_API_KEY, 
            model=settings.DEFAULT_CHAT_MODEL, 
            temperature=0.0
        )


def _enhance_query_for_domain(query: str, domain: Domain) -> str:
    """Enhance query with domain-specific terms for better retrieval."""
    domain_terms = {
        "therapy": [
            "therapy", "treatment", "psychological", "mental health", "counseling",
            "therapeutic", "intervention", "assessment", "diagnosis", "symptoms",
            "patient", "client", "session", "behavioral", "cognitive"
        ],
        "health_fitness": [
            "health", "fitness", "exercise", "nutrition", "wellness", "medical",
            "physical", "training", "diet", "body", "weight", "muscle", "cardio",
            "strength", "endurance", "recovery", "injury", "prevention"
        ],
        "literature": [
            "literature", "literary", "author", "novel", "poetry", "prose",
            "narrative", "character", "theme", "analysis", "criticism", "text",
            "writing", "style", "genre", "period", "movement", "work"
        ]
    }
    
    relevant_terms = domain_terms.get(domain, [])
    query_words = set(query.lower().split())
    
    # Add domain terms that aren't already in the query
    additional_terms = [term for term in relevant_terms 
                      if not any(word in query_words for word in term.split())]
    
    if additional_terms:
        # Add a few most relevant terms
        query += f" {' '.join(additional_terms[:3])}"
    
    return query


def _rewrite_query(original_q: str, domain: Domain) -> str:
    """Rewrite query to maximize semantic retrieval effectiveness."""
    # First, enhance with domain-specific terms
    enhanced_q = _enhance_query_for_domain(original_q, domain)
    
    # Then use LLM to create a more comprehensive query
    llm = _query_rewriter()
    prompt = ChatPromptTemplate.from_messages([
        ("system", """Rewrite the user query to maximize semantic search retrieval from a diverse document collection.

The collection contains:
- Structured data (CSV/Excel) with "Column: Value" format
- PDFs with academic and professional content
- Code files with technical documentation
- Web content (HTML/XML)
- Presentations and documents

Instructions:
1. Keep the core intent of the original query
2. Add relevant synonyms and related terms
3. Include likely column names for structured data
4. Add technical terms if applicable
5. Keep it concise but comprehensive
6. Don't change the fundamental question"""),
        ("human", "Original query: {query}\nDomain: {domain}")
    ])
    
    chain = prompt | llm | StrOutputParser()
    rewritten = chain.invoke({"query": enhanced_q, "domain": domain})
    
    return rewritten.strip()


def _retrieve_with_hybrid_strategy(
    vectorstore: PineconeVectorStore,
    query: str,
    domain: Domain,
    k: int,
    score_threshold: float = 0.3,
) -> List[Document]:
    """
    Advanced retrieval with multiple strategies:
    1. Direct semantic search
    2. Query rewriting if initial results are poor
    3. MMR for diversity
    4. Metadata filtering
    """
    from app.log import app_logger
    import time
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
    
    start_time = time.time()
    app_logger.info(f"Starting retrieval for query: '{query[:100]}...'")
    
    # Preprocess the query
    processed_query = _preprocess_query(query)
    app_logger.info(f"Query preprocessed in {time.time() - start_time:.2f}s")
    
    # Strategy 1: Direct MMR search for diversity
    retriever = vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": k,
            "fetch_k": max(30, k * 6),  # Larger fetch pool for better diversity
            "lambda_mult": 0.7  # Balance between relevance and diversity
        }
    )
    
    app_logger.info(f"About to call retriever.invoke() at {time.time() - start_time:.2f}s")
    
    # Add timeout to the main retrieval
    def _retrieve_with_timeout():
        return retriever.invoke(processed_query)
    
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_retrieve_with_timeout)
            docs = future.result(timeout=15.0)  # 15 second timeout for main retrieval
            app_logger.info(f"Retriever returned {len(docs)} docs in {time.time() - start_time:.2f}s")
    except FuturesTimeout:
        app_logger.error(f"Main retrieval timed out after 15s for query: '{query[:100]}...'")
        return []
    except Exception as e:
        app_logger.error(f"Main retrieval failed: {str(e)}")
        return []
    
    # Strategy 2: If we have few results or they seem poor, try query rewriting
    if len(docs) < k // 2:
        app_logger.info(f"Few results ({len(docs)}), trying query rewriting...")
        try:
            rewritten_query = _rewrite_query(processed_query, domain)
            app_logger.info(f"Query rewritten in {time.time() - start_time:.2f}s")
            
            # Add timeout to rewritten query retrieval
            def _retrieve_rewritten():
                return retriever.invoke(rewritten_query)
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_retrieve_rewritten)
                additional_docs = future.result(timeout=10.0)  # 10 second timeout for rewritten query
                
                # Merge results, avoiding duplicates
                seen_content = {doc.page_content for doc in docs}
                for doc in additional_docs:
                    if doc.page_content not in seen_content and len(docs) < k * 2:
                        docs.append(doc)
                        seen_content.add(doc.page_content)
                        
                app_logger.info(f"Rewritten query added {len(additional_docs)} docs in {time.time() - start_time:.2f}s")
        except FuturesTimeout:
            app_logger.warning(f"Query rewriting timed out, continuing with {len(docs)} docs")
        except Exception as e:
            app_logger.warning(f"Query rewriting failed: {str(e)}, continuing with {len(docs)} docs")
    
    # Strategy 3: Score-based filtering if supported
    try:
        app_logger.info("Trying score-based filtering...")
        # Get similarity scores to filter low-quality results
        docs_with_scores = vectorstore.similarity_search_with_score(
            processed_query, 
            k=max(k * 2, 20)
        )
        
        # Filter by score threshold and take top k
        good_docs = []
        for doc, score in docs_with_scores:
            # Note: Score interpretation may vary by backend
            # Lower scores typically mean better similarity
            if score <= (1 - score_threshold) or len(good_docs) < k // 2:
                good_docs.append(doc)
            if len(good_docs) >= k:
                break
        
        if good_docs:
            app_logger.info(f"Score filtering returned {len(good_docs)} docs in {time.time() - start_time:.2f}s")
            return good_docs
            
    except Exception as e:
        app_logger.warning(f"Score filtering not supported or failed: {str(e)}")
        # If scoring isn't supported, continue with existing docs
        pass
    
    # Strategy 4: Ensure we have diverse file types if possible
    final_docs = []
    file_types_seen = set()
    
    # First pass: prioritize different file types
    for doc in docs:
        filetype = doc.metadata.get("filetype", "unknown")
        if filetype not in file_types_seen or len(final_docs) < k // 2:
            final_docs.append(doc)
            file_types_seen.add(filetype)
        if len(final_docs) >= k:
            break
    
    # Second pass: fill remaining slots
    for doc in docs:
        if doc not in final_docs and len(final_docs) < k:
            final_docs.append(doc)
    
    app_logger.info(f"Final retrieval completed with {len(final_docs)} docs in {time.time() - start_time:.2f}s")
    return final_docs[:k]


def build_rag_chain(
    domain: Domain,
    namespace: Optional[str] = None,
    k: int = 5,
    temperature: float = 0.2,
    model: str = None,
    peek_context: bool = False,
):
    """Build an enhanced RAG chain with improved retrieval and generation."""
    
    # Use default model if none specified
    if model is None:
        model = settings.DEFAULT_CHAT_MODEL
    
    embeddings = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
        request_timeout=20.0,  # 20 second timeout for embeddings
    )

    vectorstore = PineconeVectorStore(
        index_name=_index_name(domain),
        embedding=embeddings,
        namespace=namespace,
        pinecone_api_key=settings.PINECONE_API_KEY
    )

    def _retrieve(query: str) -> List[Document]:
        from app.log import app_logger
        import time
        start = time.time()
        app_logger.info(f"Starting document retrieval for query: '{query[:50]}...'")
        docs = _retrieve_with_hybrid_strategy(
            vectorstore, 
            query, 
            domain, 
            k=k, 
            score_threshold=0.3
        )
        app_logger.info(f"Retrieved {len(docs)} documents in {time.time() - start:.2f}s")
        return docs

    # Build enhanced LCEL chain
    retrieve_node = RunnableLambda(lambda q: _retrieve(q))
    fmt_context_node = RunnableLambda(lambda docs: _format_context(docs))

    # Create the chat model using the model manager
    try:
        llm = create_chat_model(model, temperature=temperature)
    except Exception as e:
        # Fallback to OpenAI if model creation fails
        print(f"Warning: Could not create model {model}, falling back to OpenAI: {e}")
        llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY, 
            model=settings.DEFAULT_CHAT_MODEL, 
            temperature=temperature,
            request_timeout=30.0  # 30 second timeout for LLM calls
        )

    if peek_context:
        # Debug mode: return context alongside answer
        def _build_debug_response(input_data):
            context_docs = input_data["context_docs"]
            question = input_data["question"]
            context = fmt_context_node.invoke(context_docs)
            
            # Generate answer
            answer = (PROMPT | llm | StrOutputParser()).invoke({
                "context": context,
                "question": question
            })
            
            # Get model info for debugging
            model_info = get_model_info(model)
            
            return {
                "answer": answer,
                "context": context,
                "model_used": {
                    "name": model,
                    "provider": model_info.provider.value if model_info else "unknown",
                    "display_name": model_info.display_name if model_info else model
                },
                "raw_docs": [
                    {
                        "content": doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content,
                        "metadata": doc.metadata,
                        "source": doc.metadata.get("source", "Unknown")
                    }
                    for doc in context_docs
                ],
                "retrieval_info": {
                    "total_docs": len(context_docs),
                    "sources": list(set(doc.metadata.get("source", "Unknown") for doc in context_docs)),
                    "file_types": list(set(doc.metadata.get("filetype", "unknown") for doc in context_docs))
                }
            }

        chain = (
            {
                "context_docs": RunnablePassthrough() | retrieve_node,
                "question": RunnablePassthrough(),
            }
            | RunnableLambda(_build_debug_response)
        )
        return chain

    # Normal production chain with timing
    def _timed_llm_call(inputs):
        from app.log import app_logger
        import time
        start = time.time()
        app_logger.info(f"Starting LLM generation for question: '{inputs['question'][:50]}...'")
        
        # Format context
        context = fmt_context_node.invoke(inputs["context"])
        app_logger.info(f"Context formatted in {time.time() - start:.2f}s")
        
        # Generate response
        response = (PROMPT | llm | StrOutputParser()).invoke({
            "context": context,
            "question": inputs["question"]
        })
        app_logger.info(f"LLM response generated in {time.time() - start:.2f}s")
        return response
    
    chain = (
        {
            "context": RunnablePassthrough() | retrieve_node,
            "question": RunnablePassthrough(),
        }
        | RunnableLambda(_timed_llm_call)
    )
    return chain


def get_available_sources(domain: Domain, namespace: Optional[str] = None) -> Dict[str, Any]:
    """Get information about available sources in the vector store."""
    embeddings = OpenAIEmbeddings(
        model=settings.OPENAI_EMBEDDING_MODEL,
        api_key=settings.OPENAI_API_KEY,
        request_timeout=20.0,  # 20 second timeout for embeddings
    )

    vectorstore = PineconeVectorStore(
        index_name=_index_name(domain),
        embedding=embeddings,
        namespace=namespace,
        pinecone_api_key=settings.PINECONE_API_KEY
    )
    
    # Get a sample of documents to understand what's available
    try:
        sample_docs = vectorstore.similarity_search("*", k=100)  # Get a good sample
        
        sources = set()
        file_types = set()
        total_chunks = len(sample_docs)
        
        for doc in sample_docs:
            if "source" in doc.metadata:
                sources.add(doc.metadata["source"])
            if "filetype" in doc.metadata:
                file_types.add(doc.metadata["filetype"])
        
        return {
            "domain": domain,
            "namespace": namespace or "default",
            "total_chunks_sampled": total_chunks,
            "unique_sources": len(sources),
            "sources": sorted(list(sources)),
            "file_types": sorted(list(file_types)),
            "status": "available"
        }
    except Exception as e:
        return {
            "domain": domain,
            "namespace": namespace or "default",
            "error": str(e),
            "status": "error"
        }