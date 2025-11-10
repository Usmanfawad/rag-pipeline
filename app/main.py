import asyncio 
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.pinecone_admin import bootstrap_all
from app.routes import router
from app.auth_routes import router as auth_router
from app.log import log_startup, log_shutdown
from app.middleware import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    ErrorHandlingMiddleware
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_startup()
    bootstrap_all()
    yield
    log_shutdown()

app = FastAPI(
    title="Milestone II RAG",
    version="0.1.0",
    lifespan=lifespan,
    description="RAG demo for Milestone II with JWT Authentication",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add middleware (order matters - first added is outermost)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)
app.include_router(auth_router)