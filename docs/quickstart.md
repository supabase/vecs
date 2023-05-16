# Quickstart

`vecs` is a python client for managing and querying vector stores in PostgreSQL with the pgvector extension. This guide will help you get started with using Vecs.

## Installation

Requires:

- Python 3.7+

You can install vecs using pip:

```bash
pip install vecs
```

## Usage

## Connecting

Before you can interact with Vecs, create the client to communicate with Postgres:

``` python
import vecs

DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"

# create vector store client
vx = vecs.create_client(DB_CONNECTION)
```

## Create collection

You can create a collection to store vectors specifying the collections name and the number of dimensions in the vectors you intend to store.

``` python
import vecs

# create vector store client
vx = vecs.create_client("postgresql://<user>:<password>@<host>:<port>/<db_name>")

docs = vx.create_collection(name="docs", dimension=384)
```

## Get an existing collection

To access a previously created collection, use `get_collection` to retrieve it by name

``` python
import vecs

# create vector store client
vs = vecs.create_client("postgresql://<user>:<password>@<host>:<port>/<db_name>")

docs = vx.get_collection(name="docs")
```

## Upserting vectors

`vecs` combines the concepts of "insert" and "update" into "upsert". Upserting records adds them to the collection if the `id` is not present, or updates the existing record if the `id` does exist.

```python
import vecs

# create vector store client
vx = vecs.Client("postgresql://<user>:<password>@<host>:<port>/<db_name>")

# create a collection named docs with 3 dimensional vectors
docs = vx.create_collection(name="docs", dimension=3)

# add records to the collection
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
         {"year": "2012"}
        )
    ]
)
```


## Create an index

Collections can be queried immediately after being created.
However, for good performance, the collection should be indexed after records have been upserted.
If you do not create an index, calling the `query` issues a warning.

```
query does not have a covering index for cosine_similarity. See Collection.create_index
```



## Query


For example, given the setup:

```python
import vecs

# create vector store client
vx = vecs.Client("postgresql://<user>:<password>@<host>:<port>/<db_name>")

# create a collection named docs with 3 dimensional vectors
docs = vx.create_collection(name="docs", dimension=3)

# add records to the collection
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
         {"year": "2012"}
        )
    ]
)

# Create an index for fast searches
docs.create_index(measure=vecs.IndexMeasure.cosine_similarity)
```

we can

!!! warning
    Indexes are essential for good performance. See [creating an index](#create-an-index) for more info.


### Basic

The simplest form of search is to provide athe documents can we queried via

```python
docs.query(
    query_vector=[0.4,0.5,0.6],
    limit=1,
    filters={},
    measure="cosine_distance",
    include_value=False,
    include_metadata=False,
)
```

### Metadata Filtering
...