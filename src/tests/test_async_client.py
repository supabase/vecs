import pytest

import vecs


@pytest.mark.asyncio
async def test_create_async_client(clean_db: str):
    """Test creating an async client"""
    # Convert regular connection to async
    async_db = clean_db.replace("postgresql://", "postgresql+asyncpg://")
    client = await vecs.create_async_client(async_db)
    assert isinstance(client, vecs.AsyncClient)
    await client.disconnect()


@pytest.mark.asyncio
async def test_async_client_context_manager(clean_db: str):
    """Test async client as context manager"""
    async_db = clean_db.replace("postgresql://", "postgresql+asyncpg://")
    client = await vecs.create_async_client(async_db)
    async with client:
        assert isinstance(client, vecs.AsyncClient)
        assert client.vector_version is not None


@pytest.mark.asyncio
async def test_async_collection_create_and_upsert(async_client: vecs.AsyncClient):
    """Test async collection creation and upsert"""
    # Create collection
    collection = await async_client.get_or_create_collection(
        "test_collection", dimension=3
    )
    assert collection.name == "test_collection"
    assert collection.dimension == 3

    # Test upsert
    records = [
        ("id1", [1.0, 2.0, 3.0], {"type": "test"}),
        ("id2", [4.0, 5.0, 6.0], {"type": "test"}),
    ]
    await collection.upsert(records)

    # Test collection length
    length = await collection.__len__()
    assert length == 2


@pytest.mark.asyncio
async def test_async_collection_query(async_client: vecs.AsyncClient):
    """Test async collection query"""
    # Create collection and add data
    collection = await async_client.get_or_create_collection("test_query", dimension=3)

    records = [
        ("id1", [1.0, 2.0, 3.0], {"type": "test"}),
        ("id2", [4.0, 5.0, 6.0], {"type": "test"}),
        ("id3", [7.0, 8.0, 9.0], {"type": "test"}),
    ]
    await collection.upsert(records)

    # Test query
    results = await collection.query([1.0, 2.0, 3.0], limit=2)
    assert len(results) == 2
    assert results[0] == "id1"  # Should be closest match

    # Test query with metadata
    results_with_meta = await collection.query(
        [1.0, 2.0, 3.0], limit=2, include_metadata=True
    )
    assert len(results_with_meta) == 2
    assert results_with_meta[0][0] == "id1"
    assert results_with_meta[0][1] == {"type": "test"}


@pytest.mark.asyncio
async def test_async_collection_fetch_and_delete(async_client: vecs.AsyncClient):
    """Test async collection fetch and delete"""
    # Create collection and add data
    collection = await async_client.get_or_create_collection("test_fetch", dimension=3)

    records = [
        ("id1", [1.0, 2.0, 3.0], {"type": "test"}),
        ("id2", [4.0, 5.0, 6.0], {"type": "test"}),
    ]
    await collection.upsert(records)

    # Test fetch
    fetched = await collection.fetch(["id1", "id2"])
    assert len(fetched) == 2

    # Test delete
    await collection.delete(["id1"])
    length = await collection.__len__()
    assert length == 1

    # Test fetch after delete
    fetched_after_delete = await collection.fetch(["id1", "id2"])
    assert len(fetched_after_delete) == 1


@pytest.mark.asyncio
async def test_async_list_collections(async_client: vecs.AsyncClient):
    """Test async list collections"""
    # Create multiple collections
    collection1 = await async_client.get_or_create_collection(
        "collection1", dimension=3
    )
    collection2 = await async_client.get_or_create_collection(
        "collection2", dimension=4
    )

    # List collections
    collections = await async_client.list_collections()
    collection_names = [c.name for c in collections]

    assert "collection1" in collection_names
    assert "collection2" in collection_names
    assert len(collections) >= 2


@pytest.mark.asyncio
async def test_async_delete_collection(async_client: vecs.AsyncClient):
    """Test async delete collection"""
    # Create collection
    collection = await async_client.get_or_create_collection("to_delete", dimension=3)

    # Add some data
    records = [("id1", [1.0, 2.0, 3.0], {"type": "test"})]
    await collection.upsert(records)

    # Delete collection
    await async_client.delete_collection("to_delete")

    # Try to get deleted collection - should raise error
    with pytest.raises(vecs.exc.CollectionNotFound):
        await async_client.get_collection("to_delete")


@pytest.mark.asyncio
async def test_async_collection_create_index(async_client: vecs.AsyncClient):
    """Test async collection index creation"""
    # Create collection and add enough data for indexing
    collection = await async_client.get_or_create_collection("test_index", dimension=3)

    # Add data (need enough for index to be created)
    records = [
        (f"id{i}", [float(i), float(i + 1), float(i + 2)], {"i": i})
        for i in range(1100)
    ]
    await collection.upsert(records)

    # Create index
    await collection.create_index()

    # Check if index was created
    index_name = await collection.index()
    assert index_name is not None

    # Test querying with index
    results = await collection.query([1.0, 2.0, 3.0], limit=5)
    assert len(results) == 5
