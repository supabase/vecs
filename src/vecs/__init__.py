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
__version__ = "0.4.1"


__all__ = [
    "IndexArgsIVFFlat",
    "IndexArgsHSNW",
    "IndexMethod",
    "IndexMeasure",
    "Collection",
    "Client",
    "exc",
]


def create_client(
    connection_string: str, *, skip_auth: bool = True, user_id: str | None = None
) -> Client:
    """Creates a client from a Postgres connection string"""
    return Client(connection_string, skip_auth=skip_auth, user_id=user_id)
