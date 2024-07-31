import vecs


def test_upsert(client: vecs.Client) -> None:
    # Create a collection
    col1 = client.get_or_create_collection(name="col1", dimension=3)

    # Upsert some records
    col1.upsert(
        records=[
            (
                "vec0",  # the vector's identifier
                [0.1, 0.2, 0.3],  # the vector. list or np.array
                {"year": 1973},  # associated  metadata
            ),
            ("vec1", [0.7, 0.8, 0.9], {"year": 2012}),
        ]
    )

    # Creat an index on the first collection
    col1.create_index()

    # Create a second collection
    col2 = client.get_or_create_collection(name="col2", dimension=3)

    # Create an index on the second collection
    col2.create_index()

    assert col1.index is not None
    assert col2.index is not None

    assert col1.index != col2.index
