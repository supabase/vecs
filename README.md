# vecs

<p>
    <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.7+-blue.svg" alt="Python version" height="18"></a>
    <a href="https://github.com/supabase/vecs/actions">
        <img src="https://github.com/supabase/vecs/workflows/tests/badge.svg" alt="test status" height="18">
    </a>
    <a href="https://github.com/supabase/vecs/actions">
        <img src="https://github.com/supabase/vecs/workflows/pre-commit/badge.svg" alt="Pre-commit Status" height="18">
    </a>
</p>

<p>
    <a href="https://badge.fury.io/py/vecs"><img src="https://badge.fury.io/py/vecs.svg" alt="PyPI version" height="18"></a>
    <a href="https://github.com/supabase/vecs/blob/master/LICENSE"><img src="https://img.shields.io/pypi/l/markdown-subtemplate.svg" alt="License" height="18"></a>
    <a href="https://pypi.org/project/vecs/"><img src="https://img.shields.io/pypi/dm/vecs.svg" alt="Download count" height="18"></a>
</p>

---

**Documentation**: <a href="https://supabase.github.io/vecs/api/" target="_blank">https://supabase.github.io/vecs/api/</a>

**Source Code**: <a href="https://github.com/supabase/vecs" target="_blank">https://github.com/supabase/vecs</a>

---

`vecs` is a python client for managing and querying vector stores in PostgreSQL with the [pgvector extension](https://github.com/pgvector/pgvector). This guide will help you get started with using vecs.

If you don't have a Postgres database with the pgvector ready, see [hosting](https://supabase.github.io/vecs/hosting/) for easy options.

## Installation

Requires:

- Python 3.7+

You can install vecs using pip:

```sh
pip install vecs
```

## Usage

Visit the [quickstart guide](https://supabase.github.io/vecs/latest/api) for more complete info.

```python
import vecs

DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"

# create vector store client
vx = vecs.create_client(DB_CONNECTION)

# create a collection of vectors with 3 dimensions
docs = vx.get_or_create_collection(name="docs", dimension=3)

# add records to the *docs* collection
docs.upsert(
    records=[
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
    data=[0.4,0.5,0.6],              # required
    limit=1,                         # number of records to return
    filters={"year": {"$eq": 2012}}, # metadata filters
)

# Returns: ["vec1"]
```
