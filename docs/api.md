# API

`vecs` is a python client for managing and querying vector stores in PostgreSQL with the [pgvector extension](https://github.com/pgvector/pgvector). This guide will help you get started with using vecs.

If you don't have a Postgres database with the pgvector ready, see [hosting](hosting.md) for easy options.

## Installation

Requires:

- Python 3.7+

You can install vecs using pip:

```bash
pip install vecs
```

## Usage

## Connecting

Before you can interact with vecs, create the client to communicate with Postgres. If you haven't started a Postgres instance yet, see [hosting](hosting.md).
```python
import vecs

DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"

# create vector store client
vx = vecs.create_client(DB_CONNECTION)
```

## Get or Create a Collection

You can get a collection (or create if it doesn't exist), specifying the collection's name and the number of dimensions for the vectors you intend to store.

```python
docs = vx.get_or_create_collection(name="docs", dimension=3)
```

## Upserting vectors

`vecs` combines the concepts of "insert" and "update" into "upsert". Upserting records adds them to the collection if the `id` is not present, or updates the existing record if the `id` does exist.

```python
# add records to the collection
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
```

## Create an index

Collections can be queried immediately after being created.
However, for good performance, the collection should be indexed after records have been upserted.

Indexes should be created __after__ the collection has been populated with records. Building an index
on an empty collection will result in significantly reduced recall. Once the index has been created
you can still upsert new documents into the collection but you should rebuild the index if the size of
the collection more than doubles.

Only one index may exist per-collection. By default, creating an index will replace any existing index.

To create an index:

```python
##
# INSERT RECORDS HERE
##

# index the collection to be queried by cosine distance
docs.create_index(measure=vecs.IndexMeasure.cosine_distance)
```

Available options for query `measure` are:

- `vecs.IndexMeasure.cosine_distance`
- `vecs.IndexMeasure.l2_distance`
- `vecs.IndexMeasure.max_inner_product`

which correspond to different methods for comparing query vectors to the vectors in the database.

If you aren't sure which to use, stick with the default (cosine_distance) by omitting the parameter i.e.

```python
docs.create_index()
```

!!! note
    The time required to create an index grows with the number of records and size of vectors.
    For a few thousand records expect sub-minute a response in under a minute. It may take a few
    minutes for larger collections.

## Query

Given a collection `docs` with several records:

### Basic

The simplest form of search is to provide a query vector.

!!! note
    Indexes are essential for good performance. See [creating an index](#create-an-index) for more info.

    If you do not create an index, every query will return a warning
    ```text
    query does not have a covering index for cosine_similarity. See Collection.create_index
    ```
    that incldues the `IndexMeasure` you should index.



```python
docs.query(
    data=[0.4,0.5,0.6],          # required
    limit=5,                     # number of records to return
    filters={},                  # metadata filters
    measure="cosine_distance",   # distance measure to use
    include_value=False,         # should distance measure values be returned?
    include_metadata=False,      # should record metadata be returned?
)
```

Which returns a list of vector record `ids`.


### Metadata Filtering

The metadata that is associated with each record can also be filtered during a query.

As an example, `{"year": {"$eq": 2005}}` filters a `year` metadata key to be equal to 2005

In context:

```python
docs.query(
    data=[0.4,0.5,0.6],
    filters={"year": {"$eq": 2012}}, # metadata filters
)
```

For a complete reference, see the [metadata guide](concepts_metadata.md).


### Disconnect

When you're done with a collection, be sure to disconnect the client from the database.

```python
vx.disconnect()
```

alternatively, use the client as a context manager and it will automatically close the connection on exit.


```python
import vecs

DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"

# create vector store client
with vecs.create_client(DB_CONNECTION) as vx:
    # do some work here
    pass

# connections are now closed
```


## Adapters

Adapters are an optional feature to transform data before adding to or querying from a collection. Adapters make it possible to interact with a collection using only your project's native data type (eg. just raw text), rather than manually handling vectors.

For a complete list of available adapters, see [built-in adapters](concepts_adapters.md#built-in-adapters).

As an example, we'll create a collection with an adapter that chunks text into paragraphs and converts each chunk into an embedding vector using the `all-Mini-LM6-v2` model.

First, install `vecs` with optional dependencies for text embeddings:
```sh
pip install "vecs[text_embedding]"
```

Then create a collection with an adapter to chunk text into paragraphs and embed each paragraph using the `all-Mini-LM6-v2` 384 dimensional text embedding model.

```python
import vecs
from vecs.adapter import Adapter, ParagraphChunker, TextEmbedding

# create vector store client
vx = vecs.Client("postgresql://<user>:<password>@<host>:<port>/<db_name>")

# create a collection with an adapter
docs = vx.get_or_create_collection(
    name="docs",
    adapter=Adapter(
        [
            ParagraphChunker(skip_during_query=True),
            TextEmbedding(model='all-Mini-LM6-v2'),
        ]
    )
)

```

With the adapter registered against the collection, we can upsert records into the collection passing in text rather than vectors.

```python
# add records to the collection using text as the media type
docs.upsert(
    records=[
        (
         "vec0",
         "four score and ....", # <- note that we can now pass text here
         {"year": 1973}
        ),
        (
         "vec1",
         "hello, world!",
         {"year": "2012"}
        )
    ]
)
```

Similarly, we can query the collection using text.
```python

# search by text
docs.query(data="foo bar")
```



---------
## Deprecated

### Create collection

!!! note
    Deprecated: use [get_or_create_collection](#get-or-create-a-collection)

You can create a collection to store vectors specifying the collections name and the number of dimensions in the vectors you intend to store.

```python
docs = vx.create_collection(name="docs", dimension=3)
```


### Get an existing collection

!!! note
    Deprecated: use [get_or_create_collection](#get-or-create-a-collection)

To access a previously created collection, use `get_collection` to retrieve it by name

```python
docs = vx.get_collection(name="docs")
```


