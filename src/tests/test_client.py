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


def test_get_or_create_collection(client: vecs.Client) -> None:
    client.get_or_create_collection(name="resumes", dimension=1536)
    # no error is raised
    client.get_or_create_collection(name="resumes", dimension=1536)


def test_get_or_create_collection_dim_change(client: vecs.Client) -> None:
    client.get_or_create_collection(name="resumes", dimension=1536)
    with pytest.raises(vecs.exc.MismatchedDimension):
        client.get_or_create_collection(name="resumes", dimension=1)


def test_get_collection(client: vecs.Client) -> None:
    with pytest.warns(DeprecationWarning):
        with pytest.raises(vecs.exc.CollectionNotFound):
            client.get_collection(name="foo")

        client.create_collection(name="foo", dimension=384)

        foo = client.get_collection(name="foo")
    assert foo.name == "foo"


def test_list_collections(client: vecs.Client) -> None:
    assert len(client.list_collections()) == 0
    client.get_or_create_collection(name="docs", dimension=384)
    client.get_or_create_collection(name="books", dimension=1586)
    collections = client.list_collections()
    assert len(collections) == 2


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


def test_client_with_engine(clean_db: str) -> None:
    from sqlalchemy import create_engine

    engine = create_engine(clean_db)
    client = vecs.Client(engine=engine)
    assert client.vector_version != ""
    client.get_or_create_collection(name="engine_test", dimension=3)
    assert len(client.list_collections()) >= 1


def test_create_client_with_engine(clean_db: str) -> None:
    from sqlalchemy import create_engine

    engine = create_engine(clean_db)
    client = vecs.create_client(engine=engine)
    assert client.vector_version != ""
    client.get_or_create_collection(name="create_client_engine_test", dimension=3)
    assert len(client.list_collections()) >= 1


def test_client_init_validation() -> None:
    from sqlalchemy import create_engine

    # Neither connection_string nor engine provided
    with pytest.raises(
        ValueError,
        match="Exactly one of 'connection_string' or 'engine' must be provided.",
    ):
        vecs.Client()

    # Both connection_string and engine provided
    dummy_engine = create_engine("postgresql://user:pass@localhost:5432/db")
    with pytest.raises(
        ValueError,
        match="Exactly one of 'connection_string' or 'engine' must be provided.",
    ):
        vecs.Client("postgresql://user:pass@localhost:5432/db", engine=dummy_engine)
