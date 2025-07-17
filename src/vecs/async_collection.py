"""
Defines the 'AsyncCollection' class

Importing from the `vecs.async_collection` directly is not supported.
All public classes, enums, and functions are re-exported by the top level `vecs` module.
"""

from __future__ import annotations

import math
import uuid
import warnings
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple, Union

from flupy import flu
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects import postgresql

from vecs.adapter import Adapter, AdapterContext, NoOp
from vecs.collection import (
    INDEX_MEASURE_TO_OPS,
    INDEX_MEASURE_TO_SQLA_ACC,
    IndexArgsHNSW,
    IndexArgsIVFFlat,
    IndexMeasure,
    IndexMethod,
    Metadata,
    Numeric,
    Record,
    build_filters,
    build_table,
)
from vecs.exc import (
    ArgError,
    CollectionAlreadyExists,
    CollectionNotFound,
    MismatchedDimension,
)

if TYPE_CHECKING:
    from vecs.async_client import AsyncClient


class AsyncCollection:
    """
    The `vecs.AsyncCollection` class represents a collection of vectors within a PostgreSQL database with pgvector support.
    It provides async methods to manage (create, delete, fetch, upsert), index, and perform similarity searches on these vector collections.

    The collections are stored in separate tables in the database, with each vector associated with an identifier and optional metadata.

    Example usage:

        async with vecs.create_async_client(DB_CONNECTION) as vx:
            collection = await vx.get_or_create_collection(name="docs", dimension=3)
            await collection.upsert([("id1", [1, 1, 1], {"key": "value"})])
            # Further operations on 'collection'

    Public Attributes:
        name: The name of the vector collection.
        dimension: The dimension of vectors in the collection.

    Note: Some methods of this class can raise exceptions from the `vecs.exc` module if errors occur.
    """

    def __init__(
        self,
        name: str,
        dimension: int,
        client: AsyncClient,
        adapter: Optional[Adapter] = None,
    ):
        """
        Initializes a new instance of the `AsyncCollection` class.

        During expected use, developers initialize instances of `AsyncCollection` using the
        `vecs.AsyncClient` with `vecs.AsyncClient.get_or_create_collection(...)` rather than directly.

        Args:
            name (str): The name of the collection.
            dimension (int): The dimension of the vectors in the collection.
            client (AsyncClient): The async client to use for interacting with the database.
            adapter (Adapter, optional): The adapter to use for the collection.
        """
        self.client = client
        self.name = name
        self.dimension = dimension
        self.table = build_table(name, client.meta, dimension)
        self._index: Optional[str] = None
        self.adapter = adapter or Adapter(steps=[NoOp(dimension=dimension)])

        reported_dimensions = set(
            [
                x
                for x in [
                    dimension,
                    adapter.exported_dimension if adapter else None,
                ]
                if x is not None
            ]
        )
        if len(reported_dimensions) == 0:
            raise ArgError("Either dimension or adapter must provide a dimension.")
        elif len(reported_dimensions) > 1:
            raise MismatchedDimension(
                "Dimensions reported by `dimension` argument and adapter do not match."
            )

    def __repr__(self):
        """
        Returns a string representation of the `AsyncCollection` instance.

        Returns:
            str: A string representation of the `AsyncCollection` instance.
        """
        return f'vecs.AsyncCollection(name="{self.name}", dimension={self.dimension})'

    async def __len__(self) -> int:
        """
        Returns the number of vectors in the collection.

        Returns:
            int: The number of vectors in the collection.
        """
        async with self.client.AsyncSession() as sess:
            async with sess.begin():
                stmt = select(func.count()).select_from(self.table)
                result = await sess.execute(stmt)
                return result.scalar() or 0

    async def _create_if_not_exists(self):
        """
        Creates a new collection in the database if it doesn't already exist

        Returns:
            AsyncCollection: The found or created collection.
        """
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
        ).bindparams(name=self.name)
        async with self.client.AsyncSession() as sess:
            result = await sess.execute(query)
            query_result = result.fetchone()

            if query_result:
                _, collection_dimension = query_result
            else:
                collection_dimension = None

        reported_dimensions = set(
            [x for x in [self.dimension, collection_dimension] if x is not None]
        )
        if len(reported_dimensions) > 1:
            raise MismatchedDimension(
                "Dimensions reported by `dimension` argument and existing collection do not match"
            )

        if not collection_dimension:
            async with self.client.engine.begin() as conn:
                await conn.run_sync(self.table.create)

        return self

    async def _create(self):
        """
        Creates the collection.

        Returns:
            AsyncCollection: The current instance of the AsyncCollection.

        Raises:
            CollectionAlreadyExists: If a collection with the same name already exists.
        """
        collection_exists = await self.__class__._does_collection_exist(
            self.client, self.name
        )
        if collection_exists:
            raise CollectionAlreadyExists(
                "Collection with requested name already exists"
            )
        async with self.client.engine.begin() as conn:
            await conn.run_sync(self.table.create)

        await self._create_gin_index()
        return self

    async def _create_gin_index(self):
        """
        Creates a GIN index on the metadata column for efficient filtering.
        """
        unique_string = str(uuid.uuid4()).replace("-", "_")[0:7]
        async with self.client.AsyncSession() as sess:
            await sess.execute(
                text(
                    f"""
                    create index ix_meta_{unique_string}
                      on vecs."{self.table.name}"
                      using gin (metadata jsonb_path_ops);
                    """
                )
            )
            await sess.commit()

    async def _drop(self):
        """
        Drops the collection from the database.

        Returns:
            AsyncCollection: The current instance of the AsyncCollection.
        """
        from sqlalchemy.schema import DropTable

        async with self.client.AsyncSession() as sess:
            await sess.execute(DropTable(self.table, if_exists=True))
            await sess.commit()

        return self

    async def upsert(
        self, records: Iterable[Tuple[str, Any, Metadata]], skip_adapter: bool = False
    ) -> None:
        """
        Inserts or updates *vectors* records in the collection.

        Args:
            records (Iterable[Tuple[str, Any, Metadata]]): An iterable of content to upsert.
                Each record is a tuple where:
                  - the first element is a unique string identifier
                  - the second element is an iterable of numeric values or relevant input type for the
                    adapter assigned to the collection
                  - the third element is metadata associated with the vector

            skip_adapter (bool): Should the adapter be skipped while upserting. i.e. if vectors are being
                provided, rather than a media type that needs to be transformed
        """

        chunk_size = 500

        if skip_adapter:
            pipeline = flu(records).chunk(chunk_size)
        else:
            # Construct a lazy pipeline of steps to transform and chunk user input
            pipeline = flu(self.adapter(records, AdapterContext("upsert"))).chunk(
                chunk_size
            )

        async with self.client.AsyncSession() as sess:
            async with sess.begin():
                for chunk in pipeline:
                    stmt = postgresql.insert(self.table).values(chunk)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[self.table.c.id],
                        set_=dict(
                            vec=stmt.excluded.vec, metadata=stmt.excluded.metadata
                        ),
                    )
                    await sess.execute(stmt)
        return None

    async def fetch(self, ids: Iterable[str]) -> List[Record]:
        """
        Fetches vectors from the collection by their identifiers.

        Args:
            ids (Iterable[str]): An iterable of vector identifiers.

        Returns:
            List[Record]: A list of the fetched vectors.
        """
        if isinstance(ids, str):
            raise ArgError("ids must be a list of strings")

        chunk_size = 12
        records = []
        async with self.client.AsyncSession() as sess:
            async with sess.begin():
                for id_chunk in flu(ids).chunk(chunk_size):
                    stmt = select(self.table).where(self.table.c.id.in_(id_chunk))
                    result = await sess.execute(stmt)
                    chunk_records = result.all()
                    records.extend(chunk_records)
        return records

    async def delete(
        self, ids: Optional[Iterable[str]] = None, filters: Optional[Metadata] = None
    ) -> List[str]:
        """
        Asynchronously deletes vectors from the collection by matching ids or filters.

        Args:
            ids (Iterable[str], optional): An iterable of vector identifiers.
            filters (Optional[Dict], optional): Metadata filters to match vectors for deletion.

        Returns:
            List[str]: A list of the identifiers of the deleted vectors.

        Raises:
            ArgError: If both or neither of `ids` and `filters` are provided.
        """
        if ids is None and filters is None:
            raise ArgError("Either ids or filters must be provided.")

        if ids is not None and filters is not None:
            raise ArgError("Either ids or filters must be provided, not both.")

        if isinstance(ids, str):
            raise ArgError("ids must be a list of strings")

        ids = ids or []
        filters = filters or {}
        del_ids: List[str] = []

        async with self.client.AsyncSession() as sess:
            async with sess.begin():
                if ids:
                    for id_chunk in flu(ids).chunk(12):
                        stmt = (
                            delete(self.table)
                            .where(self.table.c.id.in_(id_chunk))
                            .returning(self.table.c.id)
                        )
                        result = await sess.execute(stmt)
                        del_ids.extend(result.scalars().all())

                if filters:
                    meta_filter = build_filters(self.table.c.metadata, filters)
                    stmt = (
                        delete(self.table)
                        .where(meta_filter)
                        .returning(self.table.c.id)  # type: ignore
                    )
                    result = await sess.execute(stmt)
                    del_ids.extend([r for r in result.scalars()])

        return del_ids

    async def __getitem__(self, items: str):
        """
        Asynchronously fetches a vector from the collection by its identifier.

        Args:
            items (str): The identifier of the vector.

        Returns:
            Record: The fetched vector.

        Raises:
            ArgError: If the input is not a string.
            KeyError: If no vector is found with the given ID.
        """
        if not isinstance(items, str):
            raise ArgError("items must be a string id")

        row = await self.fetch([items])

        if not row:
            raise KeyError("no item found with requested id")

        return row[0]

    async def query(
        self,
        data: Union[Iterable[Numeric], Any],
        limit: int = 10,
        filters: Optional[Dict] = None,
        measure: Union[IndexMeasure, str] = IndexMeasure.cosine_distance,
        include_value: bool = False,
        include_metadata: bool = False,
        include_vector: bool = False,
        *,
        probes: Optional[int] = None,
        ef_search: Optional[int] = None,
        skip_adapter: bool = False,
    ) -> Union[List[Record], List[str]]:
        """
        Executes a similarity search in the collection.

        The return type is dependent on arguments *include_value* and *include_metadata*

        Args:
            data (Any): The vector to use as the query.
            limit (int, optional): The maximum number of results to return. Defaults to 10.
            filters (Optional[Dict], optional): Filters to apply to the search. Defaults to None.
            measure (Union[IndexMeasure, str], optional): The distance measure to use for the search. Defaults to 'cosine_distance'.
            include_value (bool, optional): Whether to include the distance value in the results. Defaults to False.
            include_metadata (bool, optional): Whether to include the metadata in the results. Defaults to False.
            include_vector (bool, optional): Whether to include the vector in the results. Defaults to False.
            probes (Optional[Int], optional): Number of ivfflat index lists to query. Higher increases accuracy but decreases speed
            ef_search (Optional[Int], optional): Size of the dynamic candidate list for HNSW index search. Higher increases accuracy but decreases speed
            skip_adapter (bool, optional): When True, skips any associated adapter and queries using a literal vector provided to *data*

        Returns:
            Union[List[Record], List[str]]: The result of the similarity search.
        """

        if probes is None:
            probes = 10

        if ef_search is None:
            ef_search = 40

        if not isinstance(probes, int):
            raise ArgError("probes must be an integer")

        if probes < 1:
            raise ArgError("probes must be >= 1")

        if limit > 1000:
            raise ArgError("limit must be <= 1000")

        # ValueError on bad input
        try:
            imeasure = IndexMeasure(measure)
        except ValueError:
            raise ArgError("Invalid index measure")

        if not await self.is_indexed_for_measure(imeasure):
            warnings.warn(
                UserWarning(
                    f"Query does not have a covering index for {imeasure}. See Collection.create_index"
                )
            )

        if skip_adapter:
            adapted_query = [("", data, {})]
        else:
            # Adapt the query using the pipeline
            adapted_query = [
                x
                for x in self.adapter(
                    records=[("", data, {})], adapter_context=AdapterContext("query")
                )
            ]

        if len(adapted_query) != 1:
            raise ArgError("Failed to produce exactly one query vector from input")

        _, vec, _ = adapted_query[0]

        distance_lambda = INDEX_MEASURE_TO_SQLA_ACC.get(imeasure)
        if distance_lambda is None:
            # unreachable
            raise ArgError("invalid distance_measure")  # pragma: no cover

        distance_clause = distance_lambda(self.table.c.vec)(vec)

        cols = [self.table.c.id]

        if include_value:
            cols.append(distance_clause)

        if include_vector:
            cols.append(self.table.c.vec)

        if include_metadata:
            cols.append(self.table.c.metadata)

        stmt = select(*cols)
        if filters:
            stmt = stmt.filter(
                build_filters(self.table.c.metadata, filters)  # type: ignore
            )

        stmt = stmt.order_by(distance_clause)
        stmt = stmt.limit(limit)

        async with self.client.AsyncSession() as sess:
            async with sess.begin():
                # index ignored if greater than n_lists
                await sess.execute(text(f"set local ivfflat.probes = {int(probes)}"))
                if self.client._supports_hnsw():
                    await sess.execute(
                        text(f"set local hnsw.ef_search = {int(ef_search)}")
                    )
                result = await sess.execute(stmt)
                if len(cols) == 1:
                    return [str(x) for x in result.scalars().all()]
                return result.fetchall()

    @classmethod
    async def _list_collections(cls, client: AsyncClient) -> List[AsyncCollection]:
        """
        Lists all collections in the database.

        Args:
            client (AsyncClient): The async client to use for the database connection.

        Returns:
            List[AsyncCollection]: A list of all collections.
        """
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
        """
        )
        xc = []
        async with client.AsyncSession() as sess:
            result = await sess.execute(query)
            for name, dimension in result.all():
                existing_collection = cls(name, dimension, client)
                xc.append(existing_collection)
        return xc

    @classmethod
    async def _does_collection_exist(cls, client: "AsyncClient", name: str) -> bool:
        """
        PRIVATE

        Checks if a collection with a given name exists within the database

        Args:
            client (AsyncClient): The database client.
            name (str): The name of the collection

        Returns:
            Exists: Whether the collection exists or not
        """
        try:
            await client.get_collection(name)
            return True
        except CollectionNotFound:
            return False

    async def index(self) -> Optional[str]:
        """
        Returns the name of the index for the collection, if one exists.

        Returns:
            Optional[str]: The name of the index, or None if no index exists.
        """
        if self._index is None:
            query = text(
                """
            select
                pi.relname as index_name
            from
                pg_class pi                -- index info
                join pg_index i            -- extend index info
                  on pi.oid = i.indexrelid
                join pg_class pt           -- owning table info
                  on pt.oid = i.indrelid
            where
                pi.relnamespace = 'vecs'::regnamespace
                and pi.relname ilike 'ix_vector%'
                and pi.relkind = 'i'
                and pt.relname = :table_name
            """
            )
            async with self.client.AsyncSession() as sess:
                result = await sess.execute(query, {"table_name": self.name})
                ix_name = result.scalar()
            self._index = ix_name
        return self._index

    async def is_indexed_for_measure(self, measure: IndexMeasure):
        """
        Checks if the collection is indexed for the given measure.

        Args:
            measure (IndexMeasure): The measure to check for.

        Returns:
            bool: True if the collection is indexed for the measure, False otherwise.
        """
        index_name = await self.index()
        if index_name is None:
            return False
        ops = INDEX_MEASURE_TO_OPS.get(measure)
        if ops is None:
            return False

        return ops in index_name

    async def create_index(
        self,
        measure: IndexMeasure = IndexMeasure.cosine_distance,
        method: IndexMethod = IndexMethod.auto,
        index_arguments: Optional[Union[IndexArgsIVFFlat, IndexArgsHNSW]] = None,
        replace: bool = True,
    ) -> None:
        """
        Asynchronously creates an index for the collection.

        Note:
            When `vecs` creates an index on a pgvector column in PostgreSQL, it uses a multi-step
            process that enables performant indexes to be built for large collections with low end
            database hardware.

            Those steps are:

            - Creates a new table with a different name
            - Randomly selects records from the existing table
            - Inserts the random records from the existing table into the new table
            - Creates the requested vector index on the new table
            - Upserts all data from the existing table into the new table
            - Drops the existing table
            - Renames the new table to the existing tables name

            If you create dependencies (like views) on the table that underpins
            a `vecs.Collection` the `create_index` step may require you to drop those dependencies before
            it will succeed.

        Args:
            measure (IndexMeasure, optional): The measure to index for. Defaults to 'cosine_distance'.
            method (IndexMethod, optional): The indexing method to use. Defaults to 'auto'.
            index_arguments: (IndexArgsIVFFlat | IndexArgsHNSW, optional): Index type specific arguments
            replace (bool, optional): Whether to replace the existing index. Defaults to True.

        Raises:
            ArgError:
        """
        if index_arguments:
            if method == IndexMethod.auto:
                raise ArgError(
                    "Index build parameters are not allowed when using the IndexMethod.auto index."
                )
            if (
                isinstance(index_arguments, IndexArgsHNSW)
                and method != IndexMethod.hnsw
            ) or (
                isinstance(index_arguments, IndexArgsIVFFlat)
                and method != IndexMethod.ivfflat
            ):
                raise ArgError(
                    f"{index_arguments.__class__.__name__} build parameters were supplied but {method} index was specified."
                )

        # Auto-detect method if needed
        if method == IndexMethod.auto:
            if self.client._supports_hnsw():
                method = IndexMethod.hnsw
            else:
                method = IndexMethod.ivfflat

        if method == IndexMethod.hnsw and not self.client._supports_hnsw():
            raise ArgError(
                "HNSW Unavailable. Upgrade your pgvector installation to > 0.5.0 to enable HNSW support"
            )

        ops = INDEX_MEASURE_TO_OPS.get(measure)
        if ops is None:
            raise ArgError("Unknown index measure")

        unique_string = str(uuid.uuid4()).replace("-", "_")[0:7]

        async with self.client.AsyncSession() as sess:
            async with sess.begin():
                current_index = await self.index()
                if current_index is not None:
                    if replace:
                        await sess.execute(
                            text(f'DROP INDEX IF EXISTS vecs."{current_index}";')
                        )
                        self._index = None
                    else:
                        raise ArgError("replace is set to False but an index exists")

                if method == IndexMethod.ivfflat:
                    if not index_arguments:
                        result = await sess.execute(
                            select(func.count()).select_from(self.table)
                        )
                        n_records: int = result.scalar_one()
                        n_lists = (
                            int(max(n_records / 1000, 30))
                            if n_records < 1_000_000
                            else int(math.sqrt(n_records))
                        )
                    else:
                        n_lists = index_arguments.n_lists  # type: ignore

                    await sess.execute(
                        text(
                            f"""
                            CREATE INDEX ix_{ops}_ivfflat_nl{n_lists}_{unique_string}
                            ON vecs."{self.table.name}"
                            USING ivfflat (vec {ops}) WITH (lists = {n_lists})
                            """
                        )
                    )

                elif method == IndexMethod.hnsw:
                    if not index_arguments:
                        index_arguments = IndexArgsHNSW()

                    m = index_arguments.m  # type: ignore
                    ef_construction = index_arguments.ef_construction  # type: ignore

                    await sess.execute(
                        text(
                            f"""
                            CREATE INDEX ix_{ops}_hnsw_m{m}_efc{ef_construction}_{unique_string}
                            ON vecs."{self.table.name}"
                            USING hnsw (vec {ops}) WITH (m = {m}, ef_construction = {ef_construction})
                            """
                        )
                    )

        return None
