# Adapters

Adapters are an optional feature to transform data before adding to or querying from a collection. Adapters provide a customizable and modular way to express data transformations and make interacting with collections more erganomic.

Additionally, adapter transformations are applied lazily and can internally batch operations which can make them more memory and CPU efficient compared to manually executing transforms.

## Example:
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

In summary, `Adapter`s allow you to work with a collection as though they store your prefered data type natively.


## Built-in Adapters

vecs provides several built-in Adapters.

- [ParagraphChunker](#paragraphchunker)
- [TextEmbedding](#textembedding)

Have an idea for a useful adapter? [Open an issue](https://github.com/supabase/vecs/issues/new/choose) requesting it.

### ParagraphChunker

The `ParagraphChunker` `AdapterStep` splits text media into paragraphs and yields each paragraph as a separate record. That can be a useful pre-processing step when upserting large documents that contain multiple paragraphs. The `ParagraphChunker` delimits paragraphs by two consecutive line breaks `\n\n`.

`ParagrphChunker` is a pre-preocessing step and must be used in combination with another adapter step like `TextEmbedding` to transform the chunked text into a vector.


```python
from vecs.adapter import Adapter, ParagraphChunker

...

vx.get_or_create_collection(
    name="docs",
    adapter=Adapter(
        [
            ParagraphChunker(skip_during_query=True),
            ...
        ]
    )
)
```

When querying the collection, you probably do not want to chunk the text. To skip text chunking during queries, set the `skip_during_query` argument to `True`. Setting `skip_during_query` to `False` will raise an exception if the input text contains more than one paragraph.


### TextEmbedding

The `TextEmbedding` `AdapterStep` accepts text and converts it into a vector that can be consumed by the `Collection`. `TextEmbedding` supports all models available in the [`sentence_transformers`](https://www.sbert.net) package. A complete list of supported models is available in `vecs.adapter.TextEmbeddingModel`.

```python
from vecs.adapter import Adapter, TextEmbedding
...

vx.get_or_create_collection(
    name="docs",
    adapter=Adapter(
        [
            TextEmbedding(model='all-Mini-LM6-v2')
        ]
    )
)

# search by text
docs.query(data="foo bar")
```

## Interface

Adapters are objects that take in data in the form of `Iterable[Tuple[str, Any, Optional[Dict]]]` where `Tuple[str, Any, Optional[Dict]]]` represents records of `(id, media, metadata)`.

The main use of Adapters is to transform the media part of the records into a form that is ready to be ingested into the collection (like converting text into embeddings). However, Adapters can also modify the `id` or `metadata` if required.

Due to the common interface, adapters may be comprised of multiple adapter steps to create multi-stage preprocessing pipelines. For example, a multi-step adapter might first convert text into chunks and then convert each text chunk into an embedding vector.



