"""
Defines the 'Client' class

Importing from the `vecs.client` directly is not supported.
All public classes, enums, and functions are re-exported by the top level `vecs` module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from deprecated import deprecated
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from vecs.adapter import Adapter
from vecs.exc import CollectionNotFound

if TYPE_CHECKING:
    from vecs.collection import Collection


class Client:
    """
    The `vecs.Client` class serves as an interface to a PostgreSQL database with pgvector support. It facilitates
    the creation, retrieval, listing and deletion of vector collections, while managing connections to the
    database.

    A `Client` instance represents a connection to a PostgreSQL database. This connection can be used to create
    and manipulate vector collections, where each collection is a group of vector records in a PostgreSQL table.

    The `vecs.Client` class can be also supports usage as a context manager to ensure the connection to the database
    is properly closed after operations, or used directly.

    Example usage:

        DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"

        with vecs.create_client(DB_CONNECTION) as vx:
            # do some work
            pass

        # OR

        vx = vecs.create_client(DB_CONNECTION)
        # do some work
        vx.disconnect()
    """

    def __init__(self, connection_string: str):
        """
        Initialize a Client instance.

        Args:
            connection_string (str): A string representing the database connection information.
        Returns:
            None
        """
        self.engine = create_engine(connection_string)
        self.Session = sessionmaker(self.engine)

        with self.Session() as sess:
            with sess.begin():
                sess.execute(text("create schema if not exists vecs;"))
                sess.execute(text("create extension if not exists vector;"))
                self.vector_version: str = sess.execute(
                    text(
                        "select installed_version from pg_available_extensions where name = 'vector' limit 1;"
                    )
                ).scalar_one()

    def _supports_hnsw(self):
        return (
            not self.vector_version.startswith("0.4")
            and not self.vector_version.startswith("0.3")
            and not self.vector_version.startswith("0.2")
            and not self.vector_version.startswith("0.1")
            and not self.vector_version.startswith("0.0")
        )

    def get_or_create_collection(
        self,
        name: str,
        *,
        schema: str = "vecs",
        dimension: Optional[int] = None,
        adapter: Optional[Adapter] = None,
    ) -> Collection:
        """
        Get a vector collection by name, or create it if no collection with
        *name* exists.

        Args:
            name (str): The name of the collection.

        Keyword Args:
            dimension (int): The dimensionality of the vectors in the collection.
            pipeline (int): The dimensionality of the vectors in the collection.

        Returns:
            Collection: The created collection.

        Raises:
            CollectionAlreadyExists: If a collection with the same name already exists
        """
        from vecs.collection import Collection

        adapter_dimension = adapter.exported_dimension if adapter else None

        collection = Collection(
            name=name,
            dimension=dimension or adapter_dimension,  # type: ignore
            client=self,
            adapter=adapter,
            schema=schema,
        )

        return collection._create_if_not_exists()

    @deprecated("use Client.get_or_create_collection")
    def create_collection(self, name: str, dimension: int) -> Collection:
        """
        Create a new vector collection.

        Args:
            name (str): The name of the collection.
            dimension (int): The dimensionality of the vectors in the collection.

        Returns:
            Collection: The created collection.

        Raises:
            CollectionAlreadyExists: If a collection with the same name already exists
        """
        from vecs.collection import Collection

        return Collection(name, dimension, self)._create()

    @deprecated("use Client.get_or_create_collection")
    def get_collection(self, name: str) -> Collection:
        """
        Retrieve an existing vector collection.

        Args:
            name (str): The name of the collection.

        Returns:
            Collection: The retrieved collection.

        Raises:
            CollectionNotFound: If no collection with the given name exists.
        """
        from vecs.collection import Collection

        query = text(
            f"""
        select
            relname as table_name,
            atttypmod as embedding_dim
        from
            pg_class pc
            join pg_attribute pa
                on pc.oid = pa.attrelid
        where
            pc.relnamespace = 'vecs'::regnamespace
            and pc.relkind = 'r'
            and pa.attname = 'vec'
            and not pc.relname ^@ '_'
            and pc.relname = :name
        """
        ).bindparams(name=name)
        with self.Session() as sess:
            query_result = sess.execute(query).fetchone()

            if query_result is None:
                raise CollectionNotFound("No collection found with requested name")

            name, dimension = query_result
            return Collection(
                name,
                dimension,
                self,
            )

    def list_collections(self, *, schema: str = "vecs") -> List["Collection"]:
        """
        List all vector collections by database schema.

        Returns:
            list[Collection]: A list of all collections.
        """
        from vecs.collection import Collection

        return Collection._list_collections(self, schema)

    def delete_collection(self, name: str, *, schema: str = "vecs") -> None:
        """
        Delete a vector collection.

        If no collection with requested name exists, does nothing.

        Args:
            name (str): The name of the collection.
            schema (str): Optional, the database schema. Defaults to `vecs`.

        Returns:
            None
        """
        from vecs.collection import Collection

        Collection(name, -1, self, schema=schema)._drop()
        return

    def disconnect(self) -> None:
        """
        Disconnect the client from the database.

        Returns:
            None
        """
        self.engine.dispose()
        return

    def __enter__(self) -> "Client":
        """
        Enable use of the 'with' statement.

        Returns:
            Client: The current instance of the Client.
        """

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Disconnect the client on exiting the 'with' statement context.

        Args:
            exc_type: The exception type, if any.
            exc_val: The exception value, if any.
            exc_tb: The traceback, if any.

        Returns:
            None
        """
        self.disconnect()
        return
