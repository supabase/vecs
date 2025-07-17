import itertools
import random

import numpy as np
import pytest

import vecs
from vecs import IndexArgsHNSW, IndexArgsIVFFlat, IndexMethod


@pytest.mark.asyncio
async def test_async_upsert(async_client: vecs.AsyncClient) -> None:
    n_records = 100
    dim = 384

    movies = await async_client.get_or_create_collection(name="ping", dimension=dim)

    # collection initially empty
    assert await movies.__len__() == 0

    records = [
        (
            f"vec{ix}",
            vec,
            {
                "genre": random.choice(["action", "rom-com", "drama"]),
                "year": int(50 * random.random()) + 1970,
            },
        )
        for ix, vec in enumerate(np.random.random((n_records, dim)))
    ]

    # insert works
    await movies.upsert(records)
    assert await movies.__len__() == n_records

    # upserting overwrites
    new_record = ("vec0", np.zeros(384), {})
    await movies.upsert([new_record])
    db_record = await movies.__getitem__("vec0")
    assert db_record[0] == new_record[0]
    assert np.array_equal(db_record[1], new_record[1])
    assert db_record[2] == new_record[2]


@pytest.mark.asyncio
async def test_async_fetch(async_client: vecs.AsyncClient) -> None:
    n_records = 100
    dim = 384

    movies = await async_client.get_or_create_collection(name="ping", dimension=dim)

    records = [
        (
            f"vec{ix}",
            vec,
            {
                "genre": random.choice(["action", "rom-com", "drama"]),
                "year": int(50 * random.random()) + 1970,
            },
        )
        for ix, vec in enumerate(np.random.random((n_records, dim)))
    ]

    # insert works
    await movies.upsert(records)

    # test basic usage
    fetch_ids = ["vec0", "vec15", "vec99"]
    res = await movies.fetch(ids=fetch_ids)
    assert len(res) == 3
    ids = set([x[0] for x in res])
    assert all([x in ids for x in fetch_ids])

    # test one of the keys does not exist not an error
    fetch_ids = ["vec0", "vec15", "does not exist"]
    res = await movies.fetch(ids=fetch_ids)
    assert len(res) == 2

    # bad input
    with pytest.raises(vecs.exc.ArgError):
        await movies.fetch(ids="should_be_a_list")


@pytest.mark.asyncio
async def test_async_delete(async_client: vecs.AsyncClient) -> None:
    n_records = 100
    dim = 384

    movies = await async_client.get_or_create_collection(name="ping", dimension=dim)

    records = [
        (
            f"vec{ix}",
            vec,
            {
                "genre": genre,
                "year": int(50 * random.random()) + 1970,
            },
        )
        for (ix, vec), genre in zip(
            enumerate(np.random.random((n_records, dim))),
            itertools.cycle(["action", "rom-com", "drama"]),
        )
    ]

    # insert works
    await movies.upsert(records)

    # delete by IDs.
    delete_ids = ["vec0", "vec15", "vec99"]
    await movies.delete(ids=delete_ids)
    assert await movies.__len__() == n_records - len(delete_ids)

    # insert works
    await movies.upsert(records)

    # delete with filters
    genre_to_delete = "action"
    deleted_ids_by_genre = await movies.delete(
        filters={"genre": {"$eq": genre_to_delete}}
    )
    assert len(deleted_ids_by_genre) == 34

    # bad input
    with pytest.raises(vecs.exc.ArgError):
        await movies.delete(ids="should_be_a_list")

    # bad input: neither ids nor filters provided.
    with pytest.raises(vecs.exc.ArgError):
        await movies.delete()

    # bad input: should only provide either ids or filters, not both
    with pytest.raises(vecs.exc.ArgError):
        await movies.delete(ids=["vec0"], filters={"genre": {"$eq": genre_to_delete}})


@pytest.mark.asyncio
async def test_async_repr(async_client: vecs.AsyncClient) -> None:
    movies = await async_client.get_or_create_collection(name="movies", dimension=99)
    assert repr(movies) == 'vecs.AsyncCollection(name="movies", dimension=99)'


@pytest.mark.asyncio
async def test_async_getitem(async_client: vecs.AsyncClient) -> None:
    movies = await async_client.get_or_create_collection(name="movies", dimension=3)
    await movies.upsert(records=[("1", [1, 2, 3], {})])

    result = await movies.__getitem__("1")
    assert result is not None
    assert len(result) == 3

    with pytest.raises(KeyError):
        await movies.__getitem__("2")

    with pytest.raises(vecs.exc.ArgError):
        await movies.__getitem__(["only strings work not lists"])


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore:Query does")
async def test_async_query(async_client: vecs.AsyncClient) -> None:
    n_records = 100
    dim = 64

    bar = await async_client.get_or_create_collection(name="bar", dimension=dim)

    records = [
        (
            f"vec{ix}",
            vec,
            {
                "genre": random.choice(["action", "rom-com", "drama"]),
                "year": int(50 * random.random()) + 1970,
            },
        )
        for ix, vec in enumerate(np.random.random((n_records, dim)))
    ]

    await bar.upsert(records)

    _, query_vec, query_meta = await bar.__getitem__("vec5")

    top_k = 7

    res = await bar.query(
        data=query_vec,
        limit=top_k,
        filters=None,
        measure="cosine_distance",
        include_value=False,
        include_metadata=False,
    )

    # correct number of results
    assert len(res) == top_k
    # most similar to self
    assert res[0] == "vec5"

    with pytest.raises(vecs.exc.ArgError):
        await bar.query(
            data=query_vec,
            limit=1001,
        )

    with pytest.raises(vecs.exc.ArgError):
        await bar.query(
            data=query_vec,
            probes=0,
        )

    with pytest.raises(vecs.exc.ArgError):
        await bar.query(
            data=query_vec,
            probes=-1,
        )

    with pytest.raises(vecs.exc.ArgError):
        await bar.query(
            data=query_vec,
            probes="a",
        )

    with pytest.raises(vecs.exc.ArgError):
        await bar.query(data=query_vec, limit=top_k, measure="invalid")

    # skip_adapter has no effect (no adapter present)
    res = await bar.query(data=query_vec, limit=top_k, skip_adapter=True)
    assert len(res) == top_k

    # include_value
    res = await bar.query(
        data=query_vec,
        limit=top_k,
        filters=None,
        measure="cosine_distance",
        include_value=True,
    )
    assert len(res[0]) == 2
    assert res[0][0] == "vec5"
    assert pytest.approx(res[0][1]) == 0

    # include_metadata
    res = await bar.query(
        data=query_vec,
        limit=top_k,
        filters=None,
        measure="cosine_distance",
        include_metadata=True,
    )
    assert len(res[0]) == 2
    assert res[0][0] == "vec5"
    assert res[0][1] == query_meta

    # include_vector
    res = await bar.query(
        data=query_vec,
        limit=top_k,
        filters=None,
        measure="cosine_distance",
        include_vector=True,
    )
    assert len(res[0]) == 2
    assert res[0][0] == "vec5"
    assert all(res[0][1] == query_vec)

    # test for different numbers of probes
    assert len(await bar.query(data=query_vec, limit=top_k, probes=10)) == top_k

    assert len(await bar.query(data=query_vec, limit=top_k, probes=5)) == top_k

    assert len(await bar.query(data=query_vec, limit=top_k, probes=1)) == top_k

    assert len(await bar.query(data=query_vec, limit=top_k, probes=999)) == top_k


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore:Query does")
async def test_async_query_filters(async_client: vecs.AsyncClient) -> None:
    n_records = 100
    dim = 4

    bar = await async_client.get_or_create_collection(name="bar", dimension=dim)

    records = [
        (f"0", [0, 0, 0, 0], {"year": 1990}),
        (f"1", [1, 0, 0, 0], {"year": 1995}),
        (f"2", [1, 1, 0, 0], {"year": 2005}),
        (f"3", [1, 1, 1, 0], {"year": 2001}),
        (f"4", [1, 1, 1, 1], {"year": 1985}),
        (f"5", [2, 1, 1, 1], {"year": 1863}),
        (f"6", [2, 2, 1, 1], {"year": 2021}),
        (f"7", [2, 2, 2, 1], {"year": 2019}),
        (f"8", [2, 2, 2, 2], {"year": 2003}),
        (f"9", [3, 2, 2, 2], {"year": 1997}),
    ]

    await bar.upsert(records)

    query_rec = records[0]

    res = await bar.query(
        data=query_rec[1],
        limit=3,
        filters={"year": {"$lt": 1990}},
        measure="cosine_distance",
        include_value=False,
        include_metadata=False,
    )

    # Only records with year < 1990 should be returned
    assert len(res) == 2  # records 4 and 5 have years 1985 and 1863
    assert "4" in res or "5" in res

    # Test $eq filter
    res = await bar.query(
        data=query_rec[1],
        limit=10,
        filters={"year": {"$eq": 1995}},
        measure="cosine_distance",
        include_value=False,
        include_metadata=False,
    )

    assert len(res) == 1
    assert res[0] == "1"

    # Test $gt filter
    res = await bar.query(
        data=query_rec[1],
        limit=10,
        filters={"year": {"$gt": 2010}},
        measure="cosine_distance",
        include_value=False,
        include_metadata=False,
    )

    assert len(res) == 2  # records 6 and 7 have years 2021 and 2019
    assert "6" in res and "7" in res

    # Test $in filter
    res = await bar.query(
        data=query_rec[1],
        limit=10,
        filters={"year": {"$in": [1990, 1995, 2005]}},
        measure="cosine_distance",
        include_value=False,
        include_metadata=False,
    )

    assert len(res) == 3
    assert "0" in res and "1" in res and "2" in res


@pytest.mark.asyncio
async def test_async_create_index_ivfflat(async_client: vecs.AsyncClient) -> None:
    n_records = 1100
    dim = 384

    movies = await async_client.get_or_create_collection(name="movies", dimension=dim)

    records = [
        (
            f"vec{ix}",
            vec,
            {
                "genre": random.choice(["action", "rom-com", "drama"]),
                "year": int(50 * random.random()) + 1970,
            },
        )
        for ix, vec in enumerate(np.random.random((n_records, dim)))
    ]

    await movies.upsert(records)

    # Test IVFFlat index creation
    await movies.create_index(method=IndexMethod.ivfflat)
    index_name = await movies.index()
    assert index_name is not None
    assert "ivfflat" in index_name

    # Test querying with index
    query_vec = np.random.random(dim)
    results = await movies.query(data=query_vec, limit=10)
    assert len(results) == 10

    # Test with custom index arguments
    await movies.create_index(
        method=IndexMethod.ivfflat,
        index_arguments=IndexArgsIVFFlat(n_lists=50),
        replace=True,
    )
    index_name = await movies.index()
    assert index_name is not None
    assert "nl50" in index_name


@pytest.mark.asyncio
async def test_async_create_index_hnsw(async_client: vecs.AsyncClient) -> None:
    n_records = 1100
    dim = 384

    movies = await async_client.get_or_create_collection(name="movies", dimension=dim)

    records = [
        (
            f"vec{ix}",
            vec,
            {
                "genre": random.choice(["action", "rom-com", "drama"]),
                "year": int(50 * random.random()) + 1970,
            },
        )
        for ix, vec in enumerate(np.random.random((n_records, dim)))
    ]

    await movies.upsert(records)

    # Test HNSW index creation (if supported)
    if async_client._supports_hnsw():
        await movies.create_index(method=IndexMethod.hnsw)
        index_name = await movies.index()
        assert index_name is not None
        assert "hnsw" in index_name

        # Test querying with index
        query_vec = np.random.random(dim)
        results = await movies.query(data=query_vec, limit=10)
        assert len(results) == 10

        # Test with custom index arguments
        await movies.create_index(
            method=IndexMethod.hnsw,
            index_arguments=IndexArgsHNSW(m=32, ef_construction=100),
            replace=True,
        )
        index_name = await movies.index()
        assert index_name is not None
        assert "m32" in index_name and "efc100" in index_name


@pytest.mark.asyncio
async def test_async_create_index_auto(async_client: vecs.AsyncClient) -> None:
    n_records = 1100
    dim = 384

    movies = await async_client.get_or_create_collection(name="movies", dimension=dim)

    records = [
        (
            f"vec{ix}",
            vec,
            {
                "genre": random.choice(["action", "rom-com", "drama"]),
                "year": int(50 * random.random()) + 1970,
            },
        )
        for ix, vec in enumerate(np.random.random((n_records, dim)))
    ]

    await movies.upsert(records)

    # Test auto index creation
    await movies.create_index(method=IndexMethod.auto)
    index_name = await movies.index()
    assert index_name is not None

    # Should create HNSW if supported, otherwise IVFFlat
    if async_client._supports_hnsw():
        assert "hnsw" in index_name
    else:
        assert "ivfflat" in index_name


@pytest.mark.asyncio
async def test_async_index_error_cases(async_client: vecs.AsyncClient) -> None:
    movies = await async_client.get_or_create_collection(name="movies", dimension=3)

    # Test index arguments validation
    with pytest.raises(vecs.exc.ArgError):
        await movies.create_index(
            method=IndexMethod.auto, index_arguments=IndexArgsIVFFlat(n_lists=50)
        )

    with pytest.raises(vecs.exc.ArgError):
        await movies.create_index(
            method=IndexMethod.ivfflat, index_arguments=IndexArgsHNSW(m=32)
        )

    with pytest.raises(vecs.exc.ArgError):
        await movies.create_index(
            method=IndexMethod.hnsw, index_arguments=IndexArgsIVFFlat(n_lists=50)
        )


@pytest.mark.asyncio
async def test_async_list_collections(async_client: vecs.AsyncClient) -> None:
    # Create multiple collections
    await async_client.get_or_create_collection(name="test1", dimension=3)
    await async_client.get_or_create_collection(name="test2", dimension=4)
    await async_client.get_or_create_collection(name="test3", dimension=5)

    # List all collections
    collections = await async_client.list_collections()
    collection_names = [c.name for c in collections]

    assert "test1" in collection_names
    assert "test2" in collection_names
    assert "test3" in collection_names
    assert len(collections) >= 3


@pytest.mark.asyncio
async def test_async_delete_collection(async_client: vecs.AsyncClient) -> None:
    # Create a collection
    await async_client.get_or_create_collection(name="to_delete", dimension=3)

    # Add some data
    collection = await async_client.get_or_create_collection(
        name="to_delete", dimension=3
    )
    await collection.upsert([("test", [1, 2, 3], {})])

    # Delete the collection
    await async_client.delete_collection("to_delete")

    # Verify it's deleted
    with pytest.raises(vecs.exc.CollectionNotFound):
        await async_client.get_collection("to_delete")


@pytest.mark.asyncio
async def test_async_is_indexed_for_measure(async_client: vecs.AsyncClient) -> None:
    collection = await async_client.get_or_create_collection(
        name="test_indexed", dimension=384
    )

    # Add some data
    records = [(f"vec{i}", np.random.random(384), {}) for i in range(1100)]
    await collection.upsert(records)

    # Initially not indexed
    assert not await collection.is_indexed_for_measure(
        vecs.IndexMeasure.cosine_distance
    )

    # Create cosine distance index
    await collection.create_index(measure=vecs.IndexMeasure.cosine_distance)

    # Now should be indexed for cosine distance
    assert await collection.is_indexed_for_measure(vecs.IndexMeasure.cosine_distance)

    # But not for other measures
    assert not await collection.is_indexed_for_measure(vecs.IndexMeasure.l2_distance)
