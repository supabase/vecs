# Indexes

Indexes are tools for optimizing query performance of a [collection](concepts_collections.md).

Collections can be [queried](api.md/#query) without an index, but that will emit a python warning and should never be done in production.

```text
query does not have a covering index for cosine_similarity. See Collection.create_index
```

As each query vector must be checked against every record in the collection. When the number of dimensions and/or number of records becomes large, that becomes extremely slow and computationally expensive.

An index is a heuristic datastructure that pre-computes distances among key points in the vector space. It is smaller and can be traversed more quickly than the whole collection enabling __much__ more performant seraching.

Only one index may exist per-collection. An index optimizes a collection for searching according to a selected distance measure.

To create an index:

```python
docs.create_index()
```

You may optionally provide a distance measure and index method.

Available options for distance `measure` are:

- `vecs.IndexMeasure.cosine_distance`
- `vecs.IndexMeasure.l2_distance`
- `vecs.IndexMeasure.max_inner_product`

which correspond to different methods for comparing query vectors to the vectors in the database.

If you aren't sure which to use, the default of cosine_distance is the most widely compatible with off-the-shelf embedding methods.

Available options for index `method` are:

- `vecs.IndexMethod.auto`
- `vecs.IndexMethod.hnsw`
- `vecs.IndexMethod.ivfflat`

Where `auto` selects the best available index method, `hnsw` uses the [HNSW](https://github.com/pgvector/pgvector#hnsw) method and `ivfflat` uses [IVFFlat](https://github.com/pgvector/pgvector#ivfflat).

When using IVFFlat indexes, the index must be created __after__ the collection has been populated with records. Building an IVFFlat index on an empty collection will result in significantly reduced recall. You can continue upserting new documents after the index has been created, but should rebuild the index if the size of the collection more than doubles since the last index operation.

HNSW indexes can be created immediately after the collection without populating records.

To manually specify `method` and `measure`, ass them as arguments to `create_index` for example:

```python
docs.create_index(
    method=IndexMethod.hnsw,
    measure=IndexMeasure.cosine_distance,
)
```

!!! note
    The time required to create an index grows with the number of records and size of vectors.
    For a few thousand records expect sub-minute a response in under a minute. It may take a few
    minutes for larger collections.
