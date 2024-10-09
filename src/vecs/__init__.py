from vecs import exc
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
    "exc",
]


def create_client(connection_string: str) -> Client:
    """Creates a client from a Postgres connection string"""
    return Client(connection_string)
