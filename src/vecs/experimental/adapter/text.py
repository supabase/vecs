from typing import Any, Dict, Generator, Iterable, Literal, Optional, Tuple

from vecs.exc import MissingDependency

from .base import AdapterContext, AdapterStep

TextEmbeddingModel = Literal[
    "all-mpnet-base-v2",
    "multi-qa-mpnet-base-dot-v1",
    "all-distilroberta-v1",
    "all-MiniLM-L12-v2",
    "multi-qa-distilbert-cos-v1",
    "all-MiniLM-L6-v2",
    "multi-qa-MiniLM-L6-cos-v1",
    "paraphrase-multilingual-mpnet-base-v2",
    "paraphrase-albert-small-v2",
    "paraphrase-multilingual-MiniLM-L12-v2",
    "paraphrase-MiniLM-L3-v2",
    "distiluse-base-multilingual-cased-v1",
    "distiluse-base-multilingual-cased-v2",
]


class TextEmbedding(AdapterStep):
    def __init__(self, *, model: TextEmbeddingModel):
        try:
            from sentence_transformers import SentenceTransformer as ST
        except ImportError:
            raise MissingDependency(
                "Missing feature vecs[text_embedding]. Hint: `pip install 'vecs[text_embedding]'`"
            )

        self.model = ST(model)
        self._exported_dimension = self.model.get_sentence_embedding_dimension()

    @property
    def exported_dimension(self) -> Optional[int]:
        return self._exported_dimension

    def __call__(
        self,
        records: Iterable[Tuple[str, Any, Optional[Dict]]],
        adapter_context: AdapterContext,  # pyright: ignore
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        for id, media, metadata in records:
            # XXX: (optional) implement chunking to improve throughput
            embedding = self.model.encode(media, normalize_embeddings=True)
            yield (id, embedding, metadata or {})


class ParagraphChunker(AdapterStep):
    def __init__(self, *, skip_during_query: bool):
        self.skip_during_query = skip_during_query

    def __call__(
        self,
        records: Iterable[Tuple[str, Any, Optional[Dict]]],
        adapter_context: AdapterContext,
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        if adapter_context == AdapterContext("query") and self.skip_during_query:
            for id, media, metadata in records:
                yield (id, media, metadata or {})
        else:
            for id, media, metadata in records:
                paragraphs = media.split("\n\n")

                for paragraph_ix, paragraph in enumerate(paragraphs):
                    yield (
                        f"{id}_para_{str(paragraph_ix).zfill(3)}",
                        paragraph,
                        metadata or {},
                    )
