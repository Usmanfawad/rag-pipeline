import asyncio 

from typing import List, Literal, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Body

from pydantic import BaseModel

from app.pinecone_admin import bootstrap_all
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_all()
    yield

app = FastAPI(
    title="Milestone II RAG",
    version="0.1.0",
    lifespan=lifespan,
    description="RAG demo for Milestone II",

)


app.include_router(router)