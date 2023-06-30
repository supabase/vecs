"""
Defines the 'Collection' class

Importing from the `vecs.collection` directly is not supported.
All public classes, enums, and functions are re-exported by the top level `vecs` module.
"""
from __future__ import annotations

import math
import uuid
import warnings
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple, Union

from flupy import flu
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    and_,
    cast,
    delete,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects import postgresql

from vecs.exc import (
    ArgError,
    CollectionAlreadyExists,
    CollectionNotFound,
    FilterError,
    Unreachable,
)
from vecs.experimental.adapter import Adapter, AdapterContext
from vecs.experimental.adapter.noop import NoOp

if TYPE_CHECKING:
    from vecs.client import Client


MetadataValues = Union[str, int, float, bool, List[str]]
Metadata = Dict[str, MetadataValues]
Numeric = Union[int, float, complex]
Record = Tuple[str, Iterable[Numeric], Metadata]


class IndexMethod(str, Enum):
    """
    An enum representing the index methods available.

    This class currently only supports the 'ivfflat' method but may
    expand in the future.

    Attributes:
        ivfflat (str): The ivfflat index method.
    """

    ivfflat = "ivfflat"


class IndexMeasure(str, Enum):
    """
    An enum representing the types of distance measures available for indexing.

    Attributes:
        cosine_distance (str): The cosine distance measure for indexing.
        l2_distance (str): The Euclidean (L2) distance measure for indexing.
        max_inner_product (str): The maximum inner product measure for indexing.
    """

    cosine_distance = "cosine_distance"
    l2_distance = "l2_distance"
    max_inner_product = "max_inner_product"


INDEX_MEASURE_TO_OPS = {
    # Maps the IndexMeasure enum options to the SQL ops string required by
    # the pgvector `create index` statement
    IndexMeasure.cosine_distance: "vector_cosine_ops",
    IndexMeasure.l2_distance: "vector_l2_ops",
    IndexMeasure.max_inner_product: "vector_ip_ops",
}

INDEX_MEASURE_TO_SQLA_ACC = {
    IndexMeasure.cosine_distance: lambda x: x.cosine_distance,
    IndexMeasure.l2_distance: lambda x: x.l2_distance,
    IndexMeasure.max_inner_product: lambda x: x.max_inner_product,
}


class Collection:
    """
    The `vecs.Collection` class represents a collection of vectors within a PostgreSQL database with pgvector support.
    It provides methods to manage (create, delete, fetch, upsert), index, and perform similarity searches on these vector collections.

    The collections are stored in separate tables in the database, with each vector associated with an identifier and optional metadata.

    Example usage:

        with vecs.create_client(DB_CONNECTION) as vx:
            collection = vx.create_collection(name="docs", dimension=3)
            collection.upsert([("id1", [1, 1, 1], {"key": "value"})])
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
        client: Client,
        adapter: Optional[Adapter] = None,
    ):
        """
        Initializes a new instance of the `Collection` class.

        During expected use, developers initialize instances of `Collection` using the
        `vecs.Client` with `vecs.Client.create_collection(...)` rather than directly.

        Args:
            name (str): The name of the collection.
            dimension (int): The dimension of the vectors in the collection.
            client (Client): The client to use for interacting with the database.
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
            raise Exception("One of dimension or adapter must provide a dimension")
        elif len(reported_dimensions) > 1:
            raise Exception(
                "Dimensions reported by adapter, dimension, and collection do not match"
            )

    def __repr__(self):
        """
        Returns a string representation of the `Collection` instance.

        Returns:
            str: A string representation of the `Collection` instance.
        """
        return f'vecs.Collection(name="{self.name}", dimension={self.dimension})'

    def __len__(self) -> int:
        """
        Returns the number of vectors in the collection.

        Returns:
            int: The number of vectors in the collection.
        """
        with self.client.Session() as sess:
            with sess.begin():
                stmt = select(func.count()).select_from(self.table)
                return sess.execute(stmt).scalar() or 0

    def _create_if_not_exists(self):
        """
        PRIVATE

        Creates a new collection in the database if it doesn't already exist

        Returns:
            Collection: The found or created collection.
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
        with self.client.Session() as sess:
            query_result = sess.execute(query).fetchone()

            if query_result:
                _, collection_dimension = query_result
            else:
                collection_dimension = None

        reported_dimensions = set(
            [x for x in [self.dimension, collection_dimension] if x is not None]
        )
        if len(reported_dimensions) > 1:
            raise Exception(
                "Dimensions reported by adapter, dimension, and existing collection do not match"
            )

        if not collection_dimension:
            self.table.create(self.client.engine)

        return self

    def _create(self):
        """
        PRIVATE

        Creates a new collection in the database. Raises a `vecs.exc.CollectionAlreadyExists`
        exception if a collection with the specified name already exists.

        Returns:
            Collection: The newly created collection.
        """

        collection_exists = self.__class__._does_collection_exist(
            self.client, self.name
        )
        if collection_exists:
            raise CollectionAlreadyExists(
                "Collection with requested name already exists"
            )
        self.table.create(self.client.engine)
        return self

    def _drop(self):
        """
        PRIVATE

        Deletes the collection from the database. Raises a `vecs.exc.CollectionNotFound`
        exception if no collection with the specified name exists.

        Returns:
            Collection: The deleted collection.
        """
        from sqlalchemy.schema import DropTable

        with self.client.Session() as sess:
            sess.execute(DropTable(self.table, if_exists=True))
            sess.commit()

        return self

    def upsert(self, vectors: Iterable[Tuple[str, Any, Metadata]]) -> None:
        """
        Inserts or updates *vectors* records in the collection.

        Args:
            vectors (Iterable[Tuple[str, Any, Metadata]]): An iterable of vectors to upsert.
                Each vector is represented as a tuple where the first element is a unique string identifier,
                the second element is an iterable of numeric values, and the third element is metadata associated with the vector.
        """

        chunk_size = 500

        # Construct a lazy pipeline of steps to transform and chunk
        # user input
        pipeline = (
            flu(vectors)
            .map(lambda y: self.adapter(*y, AdapterContext("upsert")))
            .flatten()
            .chunk(chunk_size)
        )

        with self.client.Session() as sess:
            with sess.begin():
                for chunk in pipeline:
                    stmt = postgresql.insert(self.table).values(chunk)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[self.table.c.id],
                        set_=dict(
                            vec=stmt.excluded.vec, metadata=stmt.excluded.metadata
                        ),
                    )
                    sess.execute(stmt)
        return None

    def fetch(self, ids: Iterable[str]) -> List[Record]:
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
        with self.client.Session() as sess:
            with sess.begin():
                for id_chunk in flu(ids).chunk(chunk_size):
                    stmt = select(self.table).where(self.table.c.id.in_(id_chunk))
                    chunk_records = sess.execute(stmt)
                    records.extend(chunk_records)
        return records

    def delete(self, ids: Iterable[str]) -> List[str]:
        """
        Deletes vectors from the collection by their identifiers.

        Args:
            ids (Iterable[str]): An iterable of vector identifiers.

        Returns:
            List[str]: A list of the identifiers of the deleted vectors.
        """
        if isinstance(ids, str):
            raise ArgError("ids must be a list of strings")

        chunk_size = 12

        del_ids = list(ids)
        ids = []
        with self.client.Session() as sess:
            with sess.begin():
                for id_chunk in flu(del_ids).chunk(chunk_size):
                    stmt = (
                        delete(self.table)
                        .where(self.table.c.id.in_(id_chunk))
                        .returning(self.table.c.id)
                    )
                    ids.extend(sess.execute(stmt).scalars() or [])
        return ids

    def __getitem__(self, items):
        """
        Fetches a vector from the collection by its identifier.

        Args:
            items (str): The identifier of the vector.

        Returns:
            Record: The fetched vector.
        """
        if not isinstance(items, str):
            raise ArgError("items must be a string id")

        row = self.fetch([items])

        if row == []:
            raise KeyError("no item found with requested id")
        return row[0]

    def query(
        self,
        query_vector: Iterable[Numeric],
        limit: int = 10,
        filters: Optional[Dict] = None,
        measure: Union[IndexMeasure, str] = IndexMeasure.cosine_distance,
        include_value: bool = False,
        include_metadata: bool = False,
        *,
        probes: Optional[int] = None,
    ) -> Union[List[Record], List[str]]:
        """
        Executes a similarity search in the collection.

        The return type is dependent on arguments *include_value* and *include_metadata*

        Args:
            query_vector (Any): The vector to use as the query.
            limit (int, optional): The maximum number of results to return. Defaults to 10.
            filters (Optional[Dict], optional): Filters to apply to the search. Defaults to None.
            measure (Union[IndexMeasure, str], optional): The distance measure to use for the search. Defaults to 'cosine_distance'.
            include_value (bool, optional): Whether to include the distance value in the results. Defaults to False.
            include_metadata (bool, optional): Whether to include the metadata in the results. Defaults to False.
            probes (Optional[Int], optional): Number of ivfflat index lists to query. Higher increases accuracy but decreases speed

        Returns:
            Union[List[Record], List[str]]: The result of the similarity search.
        """

        if probes is None:
            probes = 10

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

        if not self.is_indexed_for_measure(imeasure):
            warnings.warn(
                f"Query does not have a covering index for {imeasure}. See Collection.create_index"
            )

        # Adapt the query using the pipeline
        adapted_query = [
            x
            for x in self.adapter(
                id="",
                media=query_vector,
                metadata={},
                adapter_context=AdapterContext("query"),
            )
        ]

        if len(adapted_query) != 1:
            raise Exception("Failed to produce query vector from input")

        _, vec, _ = next(iter(adapted_query))

        distance_lambda = INDEX_MEASURE_TO_SQLA_ACC.get(imeasure)
        if distance_lambda is None:
            # unreachable
            raise ArgError("invalid distance_measure")  # pragma: no cover

        distance_clause = distance_lambda(self.table.c.vec)(vec)

        cols = [self.table.c.id]

        if include_value:
            cols.append(distance_clause)

        if include_metadata:
            cols.append(self.table.c.metadata)

        stmt = select(*cols)
        if filters:
            stmt = stmt.filter(build_filters(self.table.c.metadata, filters))  # type: ignore

        stmt = stmt.order_by(distance_clause)
        stmt = stmt.limit(limit)

        with self.client.Session() as sess:
            with sess.begin():
                # index ignored if greater than n_lists
                sess.execute(
                    text("set local ivfflat.probes = :probes").bindparams(probes=probes)
                )
                if len(cols) == 1:
                    return [str(x) for x in sess.scalars(stmt).fetchall()]
                return sess.execute(stmt).fetchall() or []

    @classmethod
    def _list_collections(cls, client: "Client") -> List["Collection"]:
        """
        PRIVATE

        Retrieves all collections from the database.

        Args:
            client (Client): The database client.

        Returns:
            List[Collection]: A list of all existing collections.
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
        """
        )
        xc = []
        with client.Session() as sess:
            for name, dimension in sess.execute(query):
                existing_collection = cls(name, dimension, client)
                xc.append(existing_collection)
        return xc

    @classmethod
    def _does_collection_exist(cls, client: "Client", name: str) -> bool:
        """
        PRIVATE

        Checks if a collection with a given name exists within the database

        Args:
            client (Client): The database client.
            name (str): The name of the collection

        Returns:
            Exists: Whether the collection exists or not
        """

        try:
            client.get_collection(name)
            return True
        except CollectionNotFound:
            return False

    @property
    def index(self) -> Optional[str]:
        """
        PRIVATE

        Note:
            The `index` property is private and expected to undergo refactoring.
            Do not rely on it's output.

        Retrieves the SQL name of the collection's vector index, if it exists.

        Returns:
            Optional[str]: The name of the index, or None if no index exists.
        """

        if self._index is None:
            query = text(
                """
            select
                relname as table_name
            from
                pg_class pc
            where
                pc.relnamespace = 'vecs'::regnamespace
                and relname ilike 'ix_vector%'
                and pc.relkind = 'i'
            """
            )
            with self.client.Session() as sess:
                ix_name = sess.execute(query).scalar()
            self._index = ix_name
        return self._index

    def is_indexed_for_measure(self, measure: IndexMeasure):
        """
        Checks if the collection is indexed for a specific measure.

        Args:
            measure (IndexMeasure): The measure to check for.

        Returns:
            bool: True if the collection is indexed for the measure, False otherwise.
        """

        index_name = self.index
        if index_name is None:
            return False

        ops = INDEX_MEASURE_TO_OPS.get(measure)
        if ops is None:
            return False

        if ops in index_name:
            return True

        return False

    def create_index(
        self,
        measure: IndexMeasure = IndexMeasure.cosine_distance,
        method: IndexMethod = IndexMethod.ivfflat,
        replace=True,
    ) -> None:
        """
        Creates an index for the collection.

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
            method (IndexMethod, optional): The indexing method to use. Defaults to 'ivfflat'.
            replace (bool, optional): Whether to replace the existing index. Defaults to True.

        Raises:
            ArgError: If an invalid index method is used, or if *replace* is False and an index already exists.
        """
        if not method == IndexMethod.ivfflat:
            # at time of writing, no other methods are supported by pgvector
            raise ArgError("invalid index method")

        if replace:
            self._index = None
        else:
            if self.index is not None:
                raise ArgError("replace is set to False but an index exists")

        ops = INDEX_MEASURE_TO_OPS.get(measure)
        if ops is None:
            raise ArgError("Unknown index measure")

        # Clone the table
        clone_table = build_table(f"_{self.name}", self.client.meta, self.dimension)

        # hacky
        try:
            clone_table.drop(self.client.engine)
        except Exception:
            pass

        with self.client.Session() as sess:
            n_records: int = sess.execute(func.count(self.table.c.id)).scalar()  # type: ignore

        with self.client.Session() as sess:
            with sess.begin():
                n_index_seed = min(5000, n_records)
                clone_table.create(sess.connection())
                stmt_seed_table = clone_table.insert().from_select(
                    self.table.c,
                    select(self.table).order_by(func.random()).limit(n_index_seed),
                )
                sess.execute(stmt_seed_table)

                n_lists = (
                    int(max(n_records / 1000, 30))
                    if n_records < 1_000_000
                    else int(math.sqrt(n_records))
                )

                unique_string = str(uuid.uuid4()).replace("-", "_")[0:7]

                sess.execute(
                    text(
                        f"""
                        create index ix_{ops}_{n_lists}_{unique_string}
                          on vecs."{clone_table.name}"
                          using ivfflat (vec {ops}) with (lists={n_lists})
                        """
                    )
                )

                sess.execute(
                    text(
                        f"""
                        create index ix_meta_{unique_string}
                          on vecs."{clone_table.name}"
                          using gin ( metadata jsonb_path_ops )
                        """
                    )
                )

                # Fully populate the table
                stmt = postgresql.insert(clone_table).from_select(
                    self.table.c, select(self.table)
                )
                stmt = stmt.on_conflict_do_nothing()
                sess.execute(stmt)

                # Replace the table
                sess.execute(text(f"drop table vecs.{self.table.name};"))
                sess.execute(
                    text(
                        f"alter table vecs._{self.table.name} rename to {self.table.name};"
                    )
                )
        return None


def build_filters(json_col: Column, filters: Dict):
    """
    PRIVATE

    Builds filters for SQL query based on provided dictionary.

    Args:
        json_col (Column): The column in the database table.
        filters (Dict): The dictionary specifying filter conditions.

    Raises:
        FilterError: If filter conditions are not correctly formatted.

    Returns:
        The filter clause for the SQL query.
    """

    if not isinstance(filters, dict):
        raise FilterError("filters must be a dict")

    if len(filters) > 1:
        raise FilterError("max 1 entry per filter")

    for key, value in filters.items():
        if not isinstance(key, str):
            raise FilterError("*filters* keys must be strings")

        if key in ("$and", "$or"):
            if not isinstance(value, list):
                raise FilterError(
                    "$and/$or filters must have associated list of conditions"
                )

            if key == "$and":
                return and_(*[build_filters(json_col, subcond) for subcond in value])

            if key == "$or":
                return or_(*[build_filters(json_col, subcond) for subcond in value])

            raise Unreachable()

        if isinstance(value, dict):
            if len(value) > 1:
                raise FilterError("only one operator permitted")
            for operator, clause in value.items():
                if operator not in ("$eq", "$ne", "$lt", "$lte", "$gt", "$gte"):
                    raise FilterError("unknown operator")

                # equality of singular values can take advantage of the metadata index
                # using containment operator. Containment can not be used to test equality
                # of lists or dicts so we restrict to single values with a __len__ check.
                if operator == "$eq" and not hasattr(clause, "__len__"):
                    contains_value = cast({key: clause}, postgresql.JSONB)
                    return json_col.op("@>")(contains_value)

                matches_value = cast(clause, postgresql.JSONB)

                # handles non-singular values
                if operator == "$eq":
                    return json_col.op("->")(key) == matches_value

                elif operator == "$ne":
                    return json_col.op("->")(key) != matches_value

                elif operator == "$lt":
                    return json_col.op("->")(key) < matches_value

                elif operator == "$lte":
                    return json_col.op("->")(key) <= matches_value

                elif operator == "$gt":
                    return json_col.op("->")(key) > matches_value

                elif operator == "$gte":
                    return json_col.op("->")(key) >= matches_value
                else:
                    raise Unreachable()


def build_table(name: str, meta: MetaData, dimension: int) -> Table:
    """
    PRIVATE

    Builds a SQLAlchemy model underpinning a `vecs.Collection`.

    Args:
        name (str): The name of the table.
        meta (MetaData): MetaData instance associated with the SQL database.
        dimension: The dimension of the vectors in the collection.

    Returns:
        Table: The constructed SQL table.
    """
    return Table(
        name,
        meta,
        Column("id", String, primary_key=True),
        Column("vec", Vector(dimension), nullable=False),
        Column(
            "metadata",
            postgresql.JSONB,
            server_default=text("'{}'::jsonb"),
            nullable=False,
        ),
        extend_existing=True,
    )
