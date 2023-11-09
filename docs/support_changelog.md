# Changelog


## 0.1.0

- Initial release

## 0.2.7

- Feature: Added `vecs.Collection.disconnect()` to drop database connection
- Feature: `vecs.Client` can be used as a context maanger to auto-close connections
- Feature: Uses (indexed) containment operator `@>` for metadata equality filters where possible
- Docs: Added docstrings to all methods, functions and modules

## 0.3.0

- Feature: Collections can have `adapters` allowing upserting/querying by native media t types
- Breaking Change: Renamed argument `Collection.upsert(vectors, ...)` to `Collection.upsert(records, ...)` in support of adapters
- Breaking Change: Renamed argument `Collection.query(query_vector, ...)` to `Collection.query(data, ...)` in support of adapters

## 0.3.1

- Feature: Metadata filtering with `$in`

## 0.4.0

- Feature: pgvector 0.5.0
- Feature: HNSW index support

## 0.4.1

- Bugfix: removed errant print statement

## master

- Feature: Parameterized IVFFlat and HNSW indexes
