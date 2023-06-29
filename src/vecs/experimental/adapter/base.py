from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Generator, List, Optional, Tuple

from flupy import flu


class AdapterContext(str, Enum):
    """
    An enum representing the different contexts in which a Pipeline
    will be invoked.

    Attributes:
        upsert (str): The Collection.upsert method
        query (str): The Collection.query method
    """

    upsert = "upsert"
    query = "query"


class AdapterStep(ABC):
    """Adapts a user media into a tuple of:
        - id (str)
        - media (unknown type)
        - metadata (dict)

    if the user provides id or metadata, default production is overriden
    """

    @property
    def exported_dimension(self) -> Optional[int]:
        return None

    @abstractmethod
    def __call__(
        self,
        id: str,
        media: Any,
        metadata: Optional[Dict],
        adapter_context: AdapterContext,
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        pass


class Adapter:
    def __init__(self, steps: List[AdapterStep]):
        self.steps = steps
        if len(steps) < 1:
            raise Exception("Adapter must contain at least 1 step")

    @property
    def exported_dimension(self) -> Optional[int]:
        """The output dimension of the adapter"""
        for step in reversed(self.steps):
            step_dim = step.exported_dimension
            if step_dim is not None:
                return step_dim
        return None

    def __call__(
        self,
        id: str,
        media: Any,
        metadata: Optional[Dict],
        adapter_context: AdapterContext,
    ) -> Generator[Tuple[str, Any, Dict], None, None]:
        pipeline = flu([(id, media, metadata, adapter_context)])
        for step in self.steps:
            pipeline = pipeline.map(lambda x: step(*x)).flatten()

        yield from pipeline
