"""
Defines the 'AsyncClient' class

Importing from the `vecs.async_client` directly is not supported.
All public classes, enums, and functions are re-exported by the top level `vecs` module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from deprecated import deprecated
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vecs.adapter import Adapter
from vecs.exc import CollectionNotFound

if TYPE_CHECKING:
    from vecs.async_collection import AsyncCollection


class AsyncClient:
    """
    The `vecs.AsyncClient` class serves as an async interface to a PostgreSQL database with pgvector support.
    It facilitates the creation, retrieval, listing and deletion of vector collections, while managing
    async connections to the database.

    An `AsyncClient` instance represents an async connection to a PostgreSQL database. This connection can
    be used to create and manipulate vector collections, where each collection is a group of vector records
    in a PostgreSQL table.

    The `vecs.AsyncClient` class can also be used as an async context manager to ensure the connection
    to the database is properly closed after operations, or it can be used directly.

    Example usage:

        DB_CONNECTION = "postgresql+asyncpg://<user>:<password>@<host>:<port>/<db_name>"

        async with vecs.create_async_client(DB_CONNECTION) as vx:
            # do some work
            pass

        # OR

        vx = await vecs.create_async_client(DB_CONNECTION)
        # do some work
        await vx.disconnect()
    """

    def __init__(self, connection_string: str):
        """
        Initialize an AsyncClient instance.

        Args:
            connection_string (str): A string representing the database connection information.
                Should use 'postgresql+asyncpg://' protocol for async connections.

        Returns:
            None
        """
        # Convert regular postgresql:// URLs to postgresql+asyncpg://
        if connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        elif not connection_string.startswith("postgresql+asyncpg://"):
            # If it's not already async, assume it should be
            connection_string = (
                "postgresql+asyncpg://" + connection_string.split("://", 1)[-1]
            )

        self.engine = create_async_engine(connection_string)
        self.meta = MetaData(schema="vecs")
        self.AsyncSession = async_sessionmaker(self.engine, class_=AsyncSession)
        self.vector_version: Optional[str] = None

    async def _init_db(self):
        """Initialize the database schema and extensions."""
        async with self.AsyncSession() as sess:
            async with sess.begin():
                await sess.execute(text("create schema if not exists vecs;"))
                await sess.execute(text("create extension if not exists vector;"))
                result = await sess.execute(
                    text(
                        "select installed_version from pg_available_extensions where name = 'vector' limit 1;"
                    )
                )
                self.vector_version = result.scalar_one()

    def _supports_hnsw(self):
        return self.vector_version is not None and not self.vector_version.startswith(
            ("0.0", "0.1", "0.2", "0.3", "0.4")
        )

    async def get_or_create_collection(
        self,
        name: str,
        *,
        dimension: Optional[int] = None,
        adapter: Optional[Adapter] = None,
    ) -> AsyncCollection:
        """
        Get a vector collection by name, or create it if no collection with
        *name* exists.

        Args:
            name (str): The name of the collection.

        Keyword Args:
            dimension (int): The dimensionality of the vectors in the collection.
            adapter (Adapter): The adapter to use for the collection.

        Returns:
            AsyncCollection: The created collection.
        """
        from vecs.async_collection import AsyncCollection

        adapter_dimension = adapter.exported_dimension if adapter else None

        collection = AsyncCollection(
            name=name,
            dimension=dimension or adapter_dimension,  # type: ignore
            client=self,
            adapter=adapter,
        )

        return await collection._create_if_not_exists()

    @deprecated("use AsyncClient.get_or_create_collection")
    async def get_collection(self, name: str) -> AsyncCollection:
        """
        Retrieve an existing vector collection (async version).

        Args:
            name (str): The name of the collection.

        Returns:
            AsyncCollection: The retrieved collection.

        Raises:
            CollectionNotFound: If no collection with the given name exists.
        """
        query = text(
            """
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

        async with self.AsyncSession() as sess:
            result = await sess.execute(query)
            query_result = result.fetchone()

            if query_result is None:
                raise CollectionNotFound("No collection found with requested name")

            name, dimension = query_result
            return AsyncCollection(name, dimension, self)

    async def list_collections(self) -> List["AsyncCollection"]:
        """
        List all vector collections.

        Returns:
            list[AsyncCollection]: A list of all collections.
        """
        from vecs.async_collection import AsyncCollection

        return await AsyncCollection._list_collections(self)

    async def delete_collection(self, name: str) -> None:
        """
        Delete a vector collection.

        If no collection with requested name exists, does nothing.

        Args:
            name (str): The name of the collection.

        Returns:
            None
        """
        from vecs.async_collection import AsyncCollection

        await AsyncCollection(name, -1, self)._drop()
        return

    async def disconnect(self) -> None:
        """
        Disconnect the client from the database.

        Returns:
            None
        """
        await self.engine.dispose()
        return

    async def __aenter__(self) -> "AsyncClient":
        """
        Enable use of the 'async with' statement.

        Returns:
            AsyncClient: The current instance of the AsyncClient.
        """
        await self._init_db()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Disconnect the client on exiting the 'async with' statement context.

        Args:
            exc_type: The exception type, if any.
            exc_val: The exception value, if any.
            exc_tb: The traceback, if any.

        Returns:
            None
        """
        await self.disconnect()
        return
