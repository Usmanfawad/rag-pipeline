# Enhanced RAG Pipeline

A comprehensive Retrieval-Augmented Generation (RAG) pipeline with support for multiple file formats and optimized retrieval strategies.

## 🚀 Key Enhancements

### 📄 Extended File Format Support
The pipeline now supports **25+ file formats**:

#### Document Formats
- **PDF** (.pdf) - Research papers, reports, documentation
- **Word Documents** (.docx, .doc) - Business documents, reports
- **PowerPoint** (.pptx, .ppt) - Presentations and slides
- **Rich Text Format** (.rtf) - Cross-platform formatted text

#### Text & Markup Formats
- **Plain Text** (.txt) - Simple text files
- **Markdown** (.md, .markdown) - Documentation, README files
- **HTML** (.html, .htm) - Web content and documentation
- **XML** (.xml) - Structured data and specialized documents

#### Data Formats
- **CSV** (.csv) - Tabular data with intelligent row processing
- **Excel** (.xlsx, .xls) - Spreadsheets with multi-sheet support
- **JSON** (.json) - Structured data and API documentation

#### Code Files
- **Python** (.py) - Python source code
- **JavaScript/TypeScript** (.js, .jsx, .ts, .tsx) - Web development
- **Java** (.java) - Java applications
- **C/C++** (.c, .cpp) - System programming
- **C#** (.cs) - .NET applications
- **Go** (.go) - Go applications
- **PHP** (.php) - Web backend
- **Ruby** (.rb) - Ruby applications
- **Rust** (.rs) - Rust applications
- **Scala** (.scala) - Scala applications
- **Swift** (.swift) - iOS development
- **Kotlin** (.kt) - Android development
- **R** (.r) - Data science and statistics
- **SQL** (.sql) - Database queries
- **CSS/SCSS/Less** (.css, .scss, .less) - Stylesheets

### 🧠 Intelligent Processing Features

#### 1. **Adaptive Text Chunking**
- **Markdown-aware chunking** preserves document structure
- **Code-aware chunking** respects language syntax
- **HTML/XML chunking** maintains semantic boundaries
- **Structured data chunking** keeps related rows together

#### 2. **Enhanced Retrieval Strategies**
- **Hybrid search** combining semantic similarity and keyword matching
- **Query preprocessing** with domain-specific term expansion
- **MMR (Maximal Marginal Relevance)** for diverse results
- **Automatic query rewriting** for better context matching
- **Score-based filtering** to ensure result quality

#### 3. **Smart Metadata Handling**
- **File type detection** and encoding handling
- **Source attribution** with page/sheet/slide references
- **Deduplication** using content-based hashing
- **Batch processing** for efficient ingestion

#### 4. **Domain-Specific Optimization**
- **Therapy domain**: Mental health, treatment, assessment terms
- **Health & Fitness**: Medical, exercise, nutrition terminology
- **Literature**: Literary analysis, criticism, narrative elements

## 🏗️ Architecture

### Core Components

1. **Enhanced Ingestion (`app/ingestion.py`)**
   - Multi-format file loaders with error handling
   - Intelligent encoding detection
   - Optimal chunking strategies per file type
   - Efficient batch processing and deduplication

2. **Advanced RAG Chain (`app/rag_chain.py`)**
   - Hybrid retrieval with fallback strategies
   - Context-aware query enhancement
   - Comprehensive result formatting
   - Debug mode for development

3. **Rich API Endpoints (`app/routes.py`)**
   - File upload support for individual files
   - Folder-based batch ingestion
   - Debug chat endpoint with context inspection
   - System statistics and source management

4. **Comprehensive Schemas (`app/schemas.py`)**
   - Type-safe request/response models
   - Detailed error reporting
   - Structured metadata handling

## 🛠️ Installation & Setup

### 1. Install Dependencies
```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Environment Configuration
Create a `.env` file:
```env
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
INDEX_THERAPY=your-therapy-index
INDEX_HEALTH=your-health-index  
INDEX_LITERATURE=your-literature-index
```

### 3. Start the Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📚 API Usage

### File Upload Endpoint
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "domain=therapy" \
  -F "namespace=test" \
  -F "files=@document.pdf" \
  -F "files=@data.csv" \
  -F "files=@code.py"
```

### Chat with Documents
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "therapy",
    "question": "What are the key findings about PTSD treatment?",
    "k": 5,
    "temperature": 0.2
  }'
```

### Debug Mode (Development)
```bash
curl -X POST "http://localhost:8000/chat/debug" \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "therapy", 
    "question": "What treatment methods are discussed?",
    "k": 3
  }'
```

### Check Available Sources
```bash
curl "http://localhost:8000/sources/therapy"
```

### System Statistics
```bash
curl "http://localhost:8000/stats"
```

### Supported Formats
```bash
curl "http://localhost:8000/supported-formats"
```

## 🧪 Testing

Run the comprehensive test suite:
```bash
python test_enhanced_pipeline.py
```

This will test:
- File format support validation
- Multi-format ingestion
- Retrieval quality
- Chat functionality
- Debug mode

## 🔧 Advanced Configuration

### Custom Chunking Strategies
The system automatically selects optimal chunking based on file type:

```python
# Markdown files
MarkdownTextSplitter(chunk_size=1000, chunk_overlap=100)

# Code files  
PythonCodeTextSplitter.from_language(
    language=Language.PYTHON,
    chunk_size=800, 
    chunk_overlap=100
)

# Structured data (CSV/Excel)
RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=50, 
    separators=["\n", " | ", ".", " ", ""]
)
```

### Query Enhancement
Queries are automatically enhanced with:
- Domain-specific terminology
- Common abbreviation expansion
- Semantic similarity terms
- Context-aware rewriting

### Retrieval Strategies
1. **Direct MMR Search** - Initial semantic retrieval with diversity
2. **Query Rewriting** - Fallback with enhanced queries
3. **Score Filtering** - Quality-based result filtering
4. **Type Diversity** - Ensure diverse file type representation

## 🔍 Troubleshooting

### Common Issues

1. **Import Errors**: Install missing dependencies
   ```bash
   uv add python-docx python-pptx beautifulsoup4 lxml markdown striprtf chardet aiofiles
   ```

2. **Encoding Issues**: The system auto-detects encoding, but for problematic files:
   - Ensure files are not corrupted
   - Try converting to UTF-8 manually

3. **Low Retrieval Quality**:
   - Check document content quality
   - Verify domain matches your data
   - Use debug mode to inspect retrieved context
   - Adjust `k` parameter for more results

4. **Memory Issues with Large Files**:
   - Files are processed in batches
   - Adjust chunk sizes in ingestion settings
   - Monitor system resources

### Debug Mode Benefits
- **Context Inspection**: See exactly what documents are retrieved
- **Metadata Analysis**: Understand source attribution
- **Query Processing**: Track query enhancement steps
- **Performance Metrics**: Monitor retrieval effectiveness

## 🎯 Best Practices

### Document Preparation
1. **Clean Text**: Remove unnecessary formatting
2. **Consistent Structure**: Use headers and sections appropriately  
3. **Meaningful Filenames**: Include descriptive names
4. **Appropriate Domains**: Match content to therapy/health/literature domains

### Query Optimization
1. **Specific Questions**: Ask focused, specific questions
2. **Domain Terms**: Use terminology relevant to your domain
3. **Context**: Provide sufficient context for complex queries
4. **Iteration**: Use debug mode to refine queries

### System Monitoring
1. **Regular Stats**: Check `/stats` endpoint for system health
2. **Source Management**: Use `/sources/{domain}` to track content
3. **Performance**: Monitor response times and accuracy
4. **Cleanup**: Use `/clear/{domain}` when needed (with caution)

## 🚦 Performance Optimizations

- **Batch Processing**: Files processed in optimized batches
- **Deduplication**: Content-based hashing prevents duplicates
- **Lazy Loading**: Documents loaded on-demand
- **Caching**: Embedding and retrieval results cached
- **Parallel Processing**: Multiple files processed simultaneously

## 📈 Monitoring & Analytics

The system provides comprehensive monitoring:
- Document count per domain
- File type distribution
- Ingestion success rates
- Query response times
- Retrieval accuracy metrics

Use the `/stats` endpoint and debug mode for detailed insights.




