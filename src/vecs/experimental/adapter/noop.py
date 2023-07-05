from typing import Any, Dict, Generator, Iterable, Optional, Tuple

from .base import AdapterContext, AdapterStep


class NoOp(AdapterStep):
    def __init__(self, dimension: int):
        self.dimension = dimension

    @property
    def exported_dimension(self) -> Optional[int]:
        return self.dimension

    def __call__(
        self,
        records: Iterable[Tuple[str, Any, Optional[Dict]]],
        adapter_context: AdapterContext,  # pyright: ignore
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        for id, media, metadata in records:
            yield (id, media, metadata or {})
