# Indexes

Indexes are tools for optimizing query performance of a [collection](/vecs/concepts_collections).

Collections can be [queried](/vecs/api/#query) without an index, but that will emit a python warning and should never be done in produciton.

```
query does not have a covering index for cosine_similarity. See Collection.create_index
```

as each query vector must be checked against every record in the collection. When the number of dimensions and/or number of records becomes large, that becomes extremely slow and computationally expensive.

An index is a heuristic datastructure that pre-computes distances among key points in the vector space. It is smaller and can be traversed more quickly than the whole collection enabling __much__ more performant seraching.

Only one index may exist per-collection. An index optimizes a collection for searching according to a selected distance measure.

Available options distance measure are:

- cosine distance
- l2 distance
- max inner product

If you aren't sure which to use, stick with the default (cosine_distance) by omitting the parameter when creating indexes and querying.
