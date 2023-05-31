# vecs

<p>

<p>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.7+-blue.svg" alt="Python version" height="18"></a>
    <a href="https://badge.fury.io/py/vecs"><img src="https://badge.fury.io/py/vecs.svg" alt="PyPI version" height="18"></a>
    <a href="https://github.com/supabase/vecs/blob/master/LICENSE"><img src="https://img.shields.io/pypi/l/markdown-subtemplate.svg" alt="License" height="18"></a>
    <a href="https://pypi.org/project/vecs/"><img src="https://img.shields.io/pypi/dm/vecs.svg" alt="Download count" height="18"></a>
</p>

</p>

---

**Documentation**: <a href="https://supabase.github.io/vecs/api/" target="_blank">https://supabase.github.io/vecs/api/</a>

**Source Code**: <a href="https://github.com/supabase/vecs" target="_blank">https://github.com/supabase/vecs</a>

---


Vecs is a Python client library for managing and querying vector stores in PostgreSQL, leveraging the capabilities of the [pgvector extension](https://github.com/pgvector/pgvector).

## Overview

- Vector Management: create collections to persist and update vectors in a PostgreSQL database.
- Querying: Query vectors efficiently using measures such as cosine distance, l2 distance, or max inner product.
- Metadata: Each vector can have associated metadata, which can also be used as filters during queries.
- Hybrid Data: vecs creates its own schema and can coexist with your existing relational data


Visit the [quickstart guide](api.md) for how to get started.

## TL;DR

### Install

```bash
pip install vecs
```

### Usage


```python
import vecs

DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"

# create vector store client
vx = vecs.create_client(DB_CONNECTION)

# create a collection of vectors with 3 dimensions
docs = vx.create_collection(name="docs", dimension=3)

# add records to the *docs* collection
docs.upsert(
    vectors=[
        (
         "vec0",           # the vector's identifier
         [0.1, 0.2, 0.3],  # the vector. list or np.array
         {"year": 1973}    # associated  metadata
        ),
        (
         "vec1",
         [0.7, 0.8, 0.9],
         {"year": 2012}
        )
    ]
)

# index the collection for fast search performance
docs.create_index()

# query the collection filtering metadata for "year" = 2012
docs.query(
    query_vector=[0.4,0.5,0.6],      # required
    limit=1,                         # number of records to return
    filters={"year": {"$eq": 2012}}, # metadata filters
)

# Returns: ["vec1"]
```
