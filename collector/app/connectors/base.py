"""Interface comum dos conectores de eventos."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class BaseConnector(ABC):
    """Um conector produz eventos brutos (dict) a partir de uma fonte.

    Cada evento deve conter, quando possível, as estruturas System/EventData
    (formato Windows) ou o formato nativo da fonte — o normalizer trata ambos.
    """

    name: str = "base"

    @abstractmethod
    async def fetch(self, checkpoint: dict | None) -> AsyncIterator[dict[str, Any]]:
        """Gera eventos brutos desde o checkpoint informado."""
        raise NotImplementedError
        yield  # pragma: no cover

    async def test(self) -> tuple[bool, str]:
        return True, f"Conector {self.name} sem teste implementado"
