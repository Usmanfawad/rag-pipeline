from pinecone import Pinecone, ServerlessSpec
from app.settings import settings
import socket

def pc():
    # Preflight DNS check to provide a helpful error if DNS is misconfigured
    try:
        socket.gethostbyname("api.pinecone.io")
    except socket.gaierror as err:
        raise RuntimeError(
            "DNS cannot resolve api.pinecone.io. Switch your DNS to Google (8.8.8.8/8.8.4.4) or add a hosts entry."
        ) from err
    return Pinecone(api_key=settings.PINECONE_API_KEY)

def ensure_index(name: str, dimension: int = 1536, metric: str = "cosine"):
    client = pc()
    if not client.has_index(name):
        client.create_index(
            name=name,
            dimension=dimension,
            metric=metric,
            spec=ServerlessSpec(
                cloud=settings.PINECONE_CLOUD,
                region=settings.PINECONE_REGION
            ),
            deletion_protection="disabled",
            tags={"env": "dev"}
        )
    print(name)
    return name

def bootstrap_all():
    ensure_index(settings.INDEX_THERAPY)
    ensure_index(settings.INDEX_HEALTH)
    ensure_index(settings.INDEX_LITERATURE)