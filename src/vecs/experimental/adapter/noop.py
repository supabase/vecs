from typing import Any, Dict, Generator, Optional, Tuple

from .base import AdapterContext, AdapterStep


class NoOp(AdapterStep):
    def __init__(self, dimension: int):
        self.dimension = dimension

    @property
    def exported_dimension(self) -> Optional[int]:
        return self.dimension

    def __call__(
        self,
        id: str,
        media: Any,
        metadata: Optional[Dict],
        adapter_context: AdapterContext,
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        yield (id, media, metadata or {})
