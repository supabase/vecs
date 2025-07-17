from vecs import exc
from vecs.async_client import AsyncClient
from vecs.async_collection import AsyncCollection
from vecs.client import Client
from vecs.collection import (
    Collection,
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
)

__project__ = "vecs"
__version__ = "0.4.5"


__all__ = [
    "IndexArgsIVFFlat",
    "IndexArgsHNSW",
    "IndexMethod",
    "IndexMeasure",
    "Collection",
    "Client",
    "AsyncCollection",
    "AsyncClient",
    "exc",
]


def create_client(connection_string: str) -> Client:
    """Creates a client from a Postgres connection string"""
    return Client(connection_string)


async def create_async_client(connection_string: str) -> AsyncClient:
    """Creates an async client from a Postgres connection string"""
    client = AsyncClient(connection_string)
    await client._init_db()
    return client
