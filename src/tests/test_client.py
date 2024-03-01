import pytest

import vecs


def test_extracts_vector_version(client: vecs.Client) -> None:
    # pgvector version is sucessfully extracted
    assert client.vector_version != ""
    assert client.vector_version.count(".") >= 2


def test_create_collection(client: vecs.Client) -> None:
    with pytest.warns(DeprecationWarning):
        client.create_collection(name="docs", dimension=384)

        with pytest.raises(vecs.exc.CollectionAlreadyExists):
            client.create_collection(name="docs", dimension=384)


def test_get_collection(client: vecs.Client) -> None:
    with pytest.warns(DeprecationWarning):
        with pytest.raises(vecs.exc.CollectionNotFound):
            client.get_collection(name="foo")

        client.create_collection(name="foo", dimension=384)

        foo = client.get_collection(name="foo")
    assert foo.name == "foo"


def test_list_collections(client: vecs.Client) -> None:
    """
    Test list_collections returns appropriate results for default schema (vecs) and custom schema
    """
    assert len(client.list_collections()) == 0
    client.get_or_create_collection(name="docs", dimension=384)
    client.get_or_create_collection(name="books", dimension=1586)
    client.get_or_create_collection(name="movies", schema="test_schema", dimension=384)
    collections = client.list_collections()
    collections_test_schema = client.list_collections(schema="test_schema")
    assert len(collections) == 2
    assert len(collections_test_schema) == 1


def test_delete_collection(client: vecs.Client) -> None:
    client.get_or_create_collection(name="books", dimension=1586)
    collections = client.list_collections()
    assert len(collections) == 1

    client.delete_collection("books")

    collections = client.list_collections()
    assert len(collections) == 0

    # does not raise when does not exist
    client.delete_collection("books")


def test_dispose(client: vecs.Client) -> None:
    # Connect and disconnect in context manager
    with client:
        client.get_or_create_collection(name="books", dimension=1)
        collections = client.list_collections()
        assert len(collections) == 1

    # engine.dispose re-creates the connection pool so
    # confirm that the client can still re-connect transparently
    assert len(client.list_collections()) == 1
