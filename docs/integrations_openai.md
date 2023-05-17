# Integration: Open AI

This guide will walk you through an example integration of the OpenAI API with the vecs Python library. We will create embeddings using OpenAI's `text-embedding-ada-002` model, insert these embeddings into a PostgreSQL database using vecs, and then query vecs to find the most similar sentences to a given query sentence.

## Create an Environment

First, you need to set up your environment. You will need Python 3.7 with the `vecs` and `openai` libraries installed.

You can install the necessary Python libraries using pip:

```
pip install vecs openai
```

You'll also need:

- [An OpenAI API Key](https://platform.openai.com/account/api-keys)
- [A Postgres Database with the pgvector extension](hosting.md)

## Create Embeddings

Next, we will use OpenAI's `text-embedding-ada-002` model to create embeddings for a set of sentences.

```python
import openai

openai.api_key = '<OPENAI-API-KEY>'

dataset = [
    "The cat sat on the mat.",
    "The quick brown fox jumps over the lazy dog.",
    "Friends, Romans, countrymen, lend me your ears",
    "To be or not to be, that is the question.",
]

embeddings = []

for sentence in dataset:
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=[sentence]
    )
    embeddings.append((sentence, response["data"][0]["embedding"]))
```

### Store the Embeddings with vecs

Now that we have our embeddings, we can insert them into a PostgreSQL database using vecs.

```python
import vecs

DB_CONNECTION = "postgresql://<user>:<password>@<host>:<port>/<db_name>"

# create vector store client
vx = vecs.Client(DB_CONNECTION)

# create a collection named 'sentences' with 512 dimensional vectors (default dimension for text-embedding-ada-002)
sentences = vx.create_collection(name="sentences", dimension=1536)

# upsert the embeddings into the 'sentences' collection
sentences.upsert(vectors=embeddings)

# create an index for the 'sentences' collection
sentences.create_index()
```

### Querying for Most Similar Sentences

Finally, we can query vecs to find the most similar sentences to a given query sentence. We will first need to create an embedding for the query sentence using the `text-embedding-ada-002` model.

```python
query_sentence = "A quick animal jumps over a lazy one."

# create an embedding for the query sentence
response = openai.Embedding.create(
    model="text-embedding-ada-002",
    input=[query_sentence]
)
query_embedding = response["data"][0]["embedding"]

# query the 'sentences' collection for the most similar sentences
results = sentences.query(
    query_vector=query_embedding,
    limit=3,
    include_value = True
)

# print the results
for result in results:
    print(result)
```

Returns the most similar 3 records and their distance to the query vector.
```
('The quick brown fox jumps over the lazy dog.', 0.0633971456300456)
('The cat sat on the mat.', 0.16474785399561)
('To be or not to be, that is the question.', 0.24531234467506)
```
