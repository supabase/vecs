import random

import numpy as np
import pytest

import vecs
from vecs.collection import IndexMethod


def test_upsert(client: vecs.Client) -> None:
    n_records = 100
    dim = 384

    movies = client.get_or_create_collection(name="ping", dimension=dim)

    # collection initially empty
    assert len(movies) == 0

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
    movies.upsert(records)
    assert len(movies) == n_records

    # upserting overwrites
    new_record = ("vec0", np.zeros(384), {})
    movies.upsert([new_record])
    db_record = movies["vec0"]
    db_record[0] == new_record[0]
    db_record[1] == new_record[1]
    db_record[2] == new_record[2]


def test_fetch(client: vecs.Client) -> None:
    n_records = 100
    dim = 384

    movies = client.get_or_create_collection(name="ping", dimension=dim)

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
    movies.upsert(records)

    # test basic usage
    fetch_ids = ["vec0", "vec15", "vec99"]
    res = movies.fetch(ids=fetch_ids)
    assert len(res) == 3
    ids = set([x[0] for x in res])
    assert all([x in ids for x in fetch_ids])

    # test one of the keys does not exist not an error
    fetch_ids = ["vec0", "vec15", "does not exist"]
    res = movies.fetch(ids=fetch_ids)
    assert len(res) == 2

    # bad input
    with pytest.raises(vecs.exc.ArgError):
        movies.fetch(ids="should_be_a_list")


def test_delete(client: vecs.Client) -> None:
    n_records = 100
    dim = 384

    movies = client.get_or_create_collection(name="ping", dimension=dim)

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
    movies.upsert(records)

    delete_ids = ["vec0", "vec15", "vec99"]
    movies.delete(ids=delete_ids)
    assert len(movies) == n_records - len(delete_ids)

    # bad input
    with pytest.raises(vecs.exc.ArgError):
        movies.delete(ids="should_be_a_list")


def test_repr(client: vecs.Client) -> None:
    movies = client.get_or_create_collection(name="movies", dimension=99)
    assert repr(movies) == 'vecs.Collection(name="movies", dimension=99)'


def test_getitem(client: vecs.Client) -> None:
    movies = client.get_or_create_collection(name="movies", dimension=3)
    movies.upsert(records=[("1", [1, 2, 3], {})])

    assert movies["1"] is not None
    assert len(movies["1"]) == 3

    with pytest.raises(KeyError):
        assert movies["2"] is not None

    with pytest.raises(vecs.exc.ArgError):
        movies[["only strings work not lists"]]


@pytest.mark.filterwarnings("ignore:Query does")
def test_query(client: vecs.Client) -> None:
    n_records = 100
    dim = 64

    bar = client.get_or_create_collection(name="bar", dimension=dim)

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

    bar.upsert(records)

    _, query_vec, query_meta = bar["vec5"]

    top_k = 7

    res = bar.query(
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
        res = bar.query(
            data=query_vec,
            limit=1001,
        )

    with pytest.raises(vecs.exc.ArgError):
        res = bar.query(
            data=query_vec,
            probes=0,
        )

    with pytest.raises(vecs.exc.ArgError):
        res = bar.query(
            data=query_vec,
            probes=-1,
        )

    with pytest.raises(vecs.exc.ArgError):
        res = bar.query(
            data=query_vec,
            probes="a",  # type: ignore
        )

    with pytest.raises(vecs.exc.ArgError):
        res = bar.query(data=query_vec, limit=top_k, measure="invalid")

    # skip_adapter has no effect (no adapter present)
    res = bar.query(data=query_vec, limit=top_k, skip_adapter=True)
    assert len(res) == top_k

    # include_value
    res = bar.query(
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
    res = bar.query(
        data=query_vec,
        limit=top_k,
        filters=None,
        measure="cosine_distance",
        include_metadata=True,
    )
    assert len(res[0]) == 2
    assert res[0][0] == "vec5"
    assert res[0][1] == query_meta

    # test for different numbers of probes
    assert len(bar.query(data=query_vec, limit=top_k, probes=10)) == top_k

    assert len(bar.query(data=query_vec, limit=top_k, probes=5)) == top_k

    assert len(bar.query(data=query_vec, limit=top_k, probes=1)) == top_k

    assert len(bar.query(data=query_vec, limit=top_k, probes=999)) == top_k


@pytest.mark.filterwarnings("ignore:Query does")
def test_query_filters(client: vecs.Client) -> None:
    n_records = 100
    dim = 4

    bar = client.get_or_create_collection(name="bar", dimension=dim)

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

    bar.upsert(records)

    query_rec = records[0]

    res = bar.query(
        data=query_rec[1],
        limit=3,
        filters={"year": {"$lt": 1990}},
        measure="cosine_distance",
        include_value=False,
        include_metadata=False,
    )

    assert res

    with pytest.raises(vecs.exc.FilterError):
        bar.query(
            data=query_rec[1],
            limit=3,
            filters=["wrong type"],
            measure="cosine_distance",
        )

    with pytest.raises(vecs.exc.FilterError):
        bar.query(
            data=query_rec[1],
            limit=3,
            # multiple keys
            filters={"key1": {"$eq": "v"}, "key2": {"$eq": "v"}},
            measure="cosine_distance",
        )

    with pytest.raises(vecs.exc.FilterError):
        bar.query(
            data=query_rec[1],
            limit=3,
            # bad key
            filters={1: {"$eq": "v"}},
            measure="cosine_distance",
        )

    with pytest.raises(vecs.exc.FilterError):
        bar.query(
            data=query_rec[1],
            limit=3,
            # and requires a list
            filters={"$and": {"year": {"$eq": 1997}}},
            measure="cosine_distance",
        )

    # AND
    assert (
        len(
            bar.query(
                data=query_rec[1],
                limit=3,
                # and requires a list
                filters={
                    "$and": [
                        {"year": {"$eq": 1997}},
                        {"year": {"$eq": 1997}},
                    ]
                },
                measure="cosine_distance",
            )
        )
        == 1
    )

    # OR
    assert (
        len(
            bar.query(
                data=query_rec[1],
                limit=3,
                # and requires a list
                filters={
                    "$or": [
                        {"year": {"$eq": 1997}},
                        {"year": {"$eq": 2001}},
                    ]
                },
                measure="cosine_distance",
            )
        )
        == 2
    )

    with pytest.raises(vecs.exc.FilterError):
        bar.query(
            data=query_rec[1],
            limit=3,
            # bad value, too many conditions
            filters={"year": {"$eq": 1997, "$ne": 1998}},
            measure="cosine_distance",
        )

    with pytest.raises(vecs.exc.FilterError):
        bar.query(
            data=query_rec[1],
            limit=3,
            # bad value, unknown operator
            filters={"year": {"$no_op": 1997}},
            measure="cosine_distance",
        )

    # ne
    assert (
        len(
            bar.query(
                data=query_rec[1],
                limit=3,
                # and requires a list
                filters={"year": {"$ne": 2000}},
                measure="cosine_distance",
            )
        )
        == 3
    )

    # lte
    assert (
        len(
            bar.query(
                data=query_rec[1],
                limit=3,
                # and requires a list
                filters={"year": {"$lte": 1989}},
                measure="cosine_distance",
            )
        )
        == 2
    )

    # gt
    assert (
        len(
            bar.query(
                data=query_rec[1],
                limit=3,
                # and requires a list
                filters={"year": {"$gt": 2019}},
                measure="cosine_distance",
            )
        )
        == 1
    )

    # gte
    assert (
        len(
            bar.query(
                data=query_rec[1],
                limit=3,
                # and requires a list
                filters={"year": {"$gte": 2019}},
                measure="cosine_distance",
            )
        )
        == 2
    )


def test_filters_eq(client: vecs.Client) -> None:
    bar = client.get_or_create_collection(name="bar", dimension=4)

    records = [
        ("0", [0, 0, 0, 0], {"a": 1}),
        ("1", [1, 0, 0, 0], {"a": 2}),
        ("2", [1, 1, 0, 0], {"a": 3}),
        ("3", [1, 1, 1, 0], {"b": [1, 2]}),
        ("4", [1, 1, 1, 1], {"b": [1, 3]}),
        ("5", [1, 1, 1, 1], {"b": 1}),
        ("6", [1, 1, 1, 1], {"c": {"d": "hi"}}),
    ]

    bar.upsert(records)
    bar.create_index()

    # Simple equality of number: has match
    assert bar.query(
        data=[0, 0, 0, 0],
        limit=3,
        filters={"a": {"$eq": 1}},
    ) == ["0"]

    # Simple equality of number: no match
    assert (
        bar.query(
            data=[0, 0, 0, 0],
            limit=3,
            filters={"a": {"$eq": 5}},
        )
        == []
    )

    # Equality of array to value: no match
    assert (
        bar.query(
            data=[0, 0, 0, 0],
            limit=3,
            filters={"a": {"$eq": [1]}},
        )
        == []
    )

    # Equality of value to array: no match
    assert (
        bar.query(
            data=[0, 0, 0, 0],
            limit=3,
            filters={"b": {"$eq": 2}},
        )
        == []
    )

    # Equality of sub-array to array: no match
    assert (
        bar.query(
            data=[0, 0, 0, 0],
            limit=3,
            filters={"b": {"$eq": [1]}},
        )
        == []
    )

    # Equality of array to array: match
    assert bar.query(
        data=[0, 0, 0, 0],
        limit=3,
        filters={"b": {"$eq": [1, 2]}},
    ) == ["3"]

    # Equality of scalar to dict (key matches): no match
    assert (
        bar.query(
            data=[0, 0, 0, 0],
            limit=3,
            filters={"c": {"$eq": "d"}},
        )
        == []
    )

    # Equality of scalar to dict (value matches): no match
    assert (
        bar.query(
            data=[0, 0, 0, 0],
            limit=3,
            filters={"c": {"$eq": "hi"}},
        )
        == []
    )

    # Equality of dict to dict: match
    assert bar.query(
        data=[0, 0, 0, 0],
        limit=3,
        filters={"c": {"$eq": {"d": "hi"}}},
    ) == ["6"]


def test_filters_in(client: vecs.Client) -> None:
    bar = client.get_or_create_collection(name="bar", dimension=4)

    records = [
        ("0", [0, 0, 0, 0], {"a": 1, "b": 2}),
        ("1", [1, 0, 0, 0], {"a": [1, 2, 3]}),
        ("2", [1, 1, 0, 0], {"a": {"1": "2"}}),
        ("3", [0, 0, 0, 0], {"a": "1"}),
    ]

    bar.upsert(records)
    bar.create_index()

    # int value of "a" is contained by [1, 2]
    assert bar.query(
        data=[0, 0, 0, 0],
        limit=3,
        filters={"a": {"$in": [1, 2]}},
    ) == ["0"]

    # str value of "a" is contained by ["1", "2"]
    assert bar.query(
        data=[0, 0, 0, 0],
        limit=3,
        filters={"a": {"$in": ["1", "2"]}},
    ) == ["3"]

    with pytest.raises(vecs.exc.FilterError):
        bar.query(
            data=[0, 0, 0, 0],
            limit=3,
            filters={"a": {"$in": 1}},  # error, value should be a list
        )

    with pytest.raises(vecs.exc.FilterError):
        bar.query(
            data=[0, 0, 0, 0],
            limit=3,
            filters={"a": {"$in": [1, [2]]}},  # error, element must be scalar
        )


def test_access_index(client: vecs.Client) -> None:
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)
    assert bar.index is None


def test_create_index(client: vecs.Client) -> None:
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)

    bar.create_index()

    assert bar.index is not None

    with pytest.raises(vecs.exc.ArgError):
        bar.create_index(replace=False)

    with pytest.raises(vecs.exc.ArgError):
        bar.create_index(method="does not exist")

    with pytest.raises(vecs.exc.ArgError):
        bar.create_index(measure="does not exist")

    bar.query(
        data=[1, 2, 3, 4],
        limit=1,
        measure="cosine_distance",
    )


def test_ivfflat(client: vecs.Client) -> None:
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)
    bar.upsert([("a", [1, 2, 3, 4], {})])

    bar.create_index(method="ivfflat")  # type: ignore
    results = bar.query(data=[1, 2, 3, 4], limit=1, probes=50)
    assert len(results) == 1

    bar.create_index(method=IndexMethod.ivfflat, replace=True)  # type: ignore
    results = bar.query(
        data=[1, 2, 3, 4],
        limit=1,
    )
    assert len(results) == 1


def test_hnsw(client: vecs.Client) -> None:
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)
    bar.upsert([("a", [1, 2, 3, 4], {})])

    bar.create_index(method="hnsw")  # type: ignore
    results = bar.query(
        data=[1, 2, 3, 4],
        limit=1,
    )
    assert len(results) == 1

    bar.create_index(method=IndexMethod.hnsw, replace=True)  # type: ignore
    results = bar.query(data=[1, 2, 3, 4], limit=1, ef_search=50)
    assert len(results) == 1


def test_cosine_index_query(client: vecs.Client) -> None:
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)
    bar.upsert([("a", [1, 2, 3, 4], {})])
    bar.create_index(measure=vecs.IndexMeasure.cosine_distance)
    results = bar.query(
        data=[1, 2, 3, 4],
        limit=1,
        measure="cosine_distance",
    )
    assert len(results) == 1


def test_l2_index_query(client: vecs.Client) -> None:
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)
    bar.upsert([("a", [1, 2, 3, 4], {})])
    bar.create_index(measure=vecs.IndexMeasure.l2_distance)
    results = bar.query(
        data=[1, 2, 3, 4],
        limit=1,
        measure="l2_distance",
    )
    assert len(results) == 1


def test_max_inner_product_index_query(client: vecs.Client) -> None:
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)
    bar.upsert([("a", [1, 2, 3, 4], {})])
    bar.create_index(measure=vecs.IndexMeasure.max_inner_product)
    results = bar.query(
        data=[1, 2, 3, 4],
        limit=1,
        measure="max_inner_product",
    )
    assert len(results) == 1


def test_mismatch_measure(client: vecs.Client) -> None:
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)
    bar.upsert([("a", [1, 2, 3, 4], {})])
    bar.create_index(measure=vecs.IndexMeasure.max_inner_product)
    with pytest.warns(UserWarning):
        results = bar.query(
            data=[1, 2, 3, 4],
            limit=1,
            # wrong measure
            measure="cosine_distance",
        )
    assert len(results) == 1


def test_is_indexed_for_measure(client: vecs.Client) -> None:
    bar = client.get_or_create_collection(name="bar", dimension=4)

    bar.create_index(measure=vecs.IndexMeasure.max_inner_product)
    assert not bar.is_indexed_for_measure("invalid")  # type: ignore
    assert bar.is_indexed_for_measure(vecs.IndexMeasure.max_inner_product)
    assert not bar.is_indexed_for_measure(vecs.IndexMeasure.cosine_distance)

    bar.create_index(measure=vecs.IndexMeasure.cosine_distance, replace=True)
    assert bar.is_indexed_for_measure(vecs.IndexMeasure.cosine_distance)


def test_failover_ivfflat(client: vecs.Client) -> None:
    """Test that index fails over to ivfflat on 0.4.0
    This is already covered by CI's test matrix but it is convenient for faster feedback
    to include it when running on the latest version of pgvector
    """
    client.vector_version = "0.4.1"
    dim = 4
    bar = client.get_or_create_collection(name="bar", dimension=dim)
    bar.upsert([("a", [1, 2, 3, 4], {})])
    # this executes an otherwise uncovered line of code that selects ivfflat when mode is 'auto'
    # and hnsw is unavailable
    bar.create_index(method=IndexMethod.auto)
