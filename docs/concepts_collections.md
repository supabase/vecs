# Collections

A collection is an group of vector records.
Records can be [added to or updated in](/vecs/quickstart/#upserting-vectors) a collection.
Collections can be [queried](/vecs/quickstart/#query) at any time, but should be [indexed](/vecs/quickstart/#create-an-index) for scalable query performance.

Each vector record has the form:

```
Record (
    id: String
    vec: Numeric[]
    metadata: JSON
)
```

For example:
```python
("vec1", [0.1, 0.2, 0.3], {"year": 1990})
```

Underneath every `vecs` a collection is Postgres table

```sql
create table <collection_name> (
    id string primary key,
    vec vector(<dimension>),
    metadata jsonb
)
```
where rows in the table map 1:1 with vecs vector records.

It is safe to select collection tables from outside the vecs client but issuing DDL is not recommended.