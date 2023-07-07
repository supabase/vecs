from itertools import zip_longest

import numpy as np
import pytest

import vecs
from vecs.adapter import Adapter, AdapterContext, AdapterStep
from vecs.adapter.noop import NoOp
from vecs.adapter.text import ParagraphChunker, TextEmbedding
from vecs.exc import ArgError, MismatchedDimension


def test_create_collection_with_adapter(client: vecs.Client) -> None:
    client.get_or_create_collection(
        name="ping",
        adapter=Adapter([TextEmbedding(model="all-MiniLM-L6-v2")]),
    )
    # Mismatched between existing collection dim (384) and provided dimension (1)
    with pytest.raises(MismatchedDimension):
        client.get_or_create_collection(name="ping", dimension=1)

    # Mismatched between dim arg and exported dim from adapter
    with pytest.raises(MismatchedDimension):
        client.get_or_create_collection(
            name="pong",
            dimension=9,
            adapter=Adapter([TextEmbedding(model="all-MiniLM-L6-v2")]),
        )

    client.get_or_create_collection(
        name="foo",
        dimension=16,
    )
    # Mismatched between exported dim from adapter and existing collection
    with pytest.raises(MismatchedDimension):
        client.get_or_create_collection(
            name="foo",
            adapter=Adapter([TextEmbedding(model="all-MiniLM-L6-v2")]),
        )

    # No detectable dimension
    with pytest.raises(ArgError):
        client.get_or_create_collection(name="foo")


def test_adapter_with_no_steps_error() -> None:
    with pytest.raises(ArgError):
        adapter = Adapter(steps=[])


def test_adapter_step_has_default_exported_dim() -> None:
    assert ParagraphChunker(skip_during_query=True).exported_dimension is None


def test_adapter_does_not_export_dimension() -> None:
    class Dummy(AdapterStep):
        def __call__(
            self,
            records,
            adapter_context,
        ):
            raise Exception("not relevant to the test")

    adapter_step = Dummy()
    assert adapter_step.exported_dimension is None
    assert Adapter([adapter_step]).exported_dimension is None


def test_noop_adapter_dimension() -> None:
    noop = NoOp(dimension=9)
    assert noop.exported_dimension == 9


def test_paragraph_chunker_adapter() -> None:
    chunker = ParagraphChunker(skip_during_query=True)
    res = [
        x
        for x in chunker(
            [("1", "first para\n\nnext para", {})], AdapterContext("upsert")
        )
    ]
    assert res == [("1_para_000", "first para", {}), ("1_para_001", "next para", {})]

    res = [
        x
        for x in chunker([("", "first para\n\nnext para", {})], AdapterContext("query"))
    ]
    assert res == [("", "first para\n\nnext para", {})]


def test_text_embedding_adapter() -> None:
    emb = TextEmbedding(model="all-MiniLM-L6-v2")

    records = [
        ("1", "first one", {"a": 1}),
        ("2", "next one", {"a": 2}),
        ("3", "last one", {"a": 3}),
    ]
    res = [x for x in emb(records, AdapterContext("upsert"))]
    assert len(res) == 3
    assert res[0][0] == "1"
    assert res[0][2] == {"a": 1}
    assert len(res[0][1]) == 384

    # test larger batch size does not impact result
    ada = TextEmbedding(model="all-MiniLM-L6-v2", batch_size=2)
    res_batch = [x for x in ada(records, AdapterContext("upsert"))]
    for (l_id, l_vec, l_meta), (r_id, r_vec, r_meta) in zip_longest(res, res_batch):  # type: ignore
        assert l_id == r_id
        assert np.allclose(l_vec, r_vec, rtol=0.003)
        assert l_meta == r_meta


def test_text_integration_adapter(client: vecs.Client) -> None:
    docs = client.get_or_create_collection(
        name="docs",
        adapter=Adapter(
            [
                ParagraphChunker(skip_during_query=False),
                TextEmbedding(model="all-MiniLM-L6-v2"),
            ]
        ),
    )

    docs.upsert(
        [
            ("1", "world hello", {"a": 1}),
            ("2", "foo bar", {}),
            ("3", "bar baz", {}),
            ("4", "long text\n\nshould split", {}),
        ]
    )

    docs.create_index()

    res = docs.query(data="hi", limit=1)
    assert res == ["1_para_000"]

    # the last record in the dataset should be split by the paragraph chunker
    res = docs.query(data="hi", limit=10)
    assert len(res) == 5

    # providing a vector works if you skip the adapter

    docs.upsert(
        [
            ("6", np.zeros(384), {}),
            ("7", np.zeros(384), {}),
        ],
        skip_adapter=True,
    )

    res = docs.query(data=np.zeros(384), limit=2, skip_adapter=True)
    assert len(res) == 2

    with pytest.raises(ArgError):
        # if the cardinality changes due to adapter pre-processing, raise an error
        docs.query(data="I split \n\n into multiple records \n\n not good")
