# Adapters

Adapters are an optional feature to transform data before adding to or querying from a collection. Adapters provide a customizable and modular way to express data transformations and make interacting with collections more erganomic.


## Interface

Adapters are objects that take in data in the form of `Iterable[Tuple[str, Any, Optional[Dict]]]` where `Tuple[str, Any, Optional[Dict]]]` represents records of `(id, media, metadata)`.

The main use of Adapters is to transform the media part of the records into a form that is ready to be ingested into the collection (like converting text into embeddings). However, Adapters can also modify the id or metadata if required.

Due to the common interface, adapters may be comprised of multiple adapter steps to create multi-stage preprocessing pipelines. For example, a multi-step adapter might first convert text into chunks and then convert each text chunk into an embedding vector.

## Example:
As an example, we'll create a collection with an adapter that chunks text into paragraphs and converts each chunk into an embedding vector using the `all-Mini-LM6-v2` model.

First, install `vecs` with optional dependencies for text embeddings
```sh
pip install "vecs[text_adapters]"
```

Then create a collection with an adapter to chunk text into paragraphs and embed each paragraph using the `all-Mini-LM6-v2` 384 dimensional text embedding model.

```python
import vecs
from vecs.adapter import Adapter
from vecs.adapter.text import ParagraphChunker, TextEmbedding

# create vector store client
DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"
vx = vecs.Client(DB_CONNECTION)

# create a collection named docs with 3 dimensional vectors
docs = vx.get_or_create_collection(
    name="docs",
    adapter=Adapter(
        [
            ParagraphChunker(),
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


## Built-in Adapters

vecs provides several built-in Adapters.

- ParagraphChunker
- TextEmbedding
- NoOp


# TODO: add section for each adapter type
