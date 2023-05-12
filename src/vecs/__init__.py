from vecs.client import Client
from vecs.collection import Collection, IndexMeasure, IndexMethod
from vecs import exc

__project__ = "vecs"
__version__ = "0.1.0"


__all__ = ["IndexMethod", "IndexMeasure", "Collection", "Client", "exc"]


def create_client(connection_string: str) -> Client:
    """Creates a client from a Postgres connection string"""
    return Client(connection_string)
