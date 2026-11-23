"""Contrato independiente de proveedor para los recolectores."""

from dataclasses import dataclass, field
from datetime import datetime
from threading import Event
from typing import Any, Iterator, Protocol


@dataclass(frozen=True)
class CollectorCapabilities:
    server_date_filter: bool = False
    pagination: bool = True
    media_download: bool = False
    cancellation: str = "between_results"


@dataclass(frozen=True)
class Advertiser:
    id: str


@dataclass
class CollectedAd:
    id: str
    delivery_start_time: datetime | None
    page: Advertiser | None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy of source content so ingestion cannot mutate the collector payload."""
        from copy import deepcopy
        return deepcopy(self.payload)


class CollectorError(RuntimeError):
    """Fallo de fuente; los resultados ya emitidos siguen siendo validos."""


class CollectorCancelled(CollectorError):
    """Cancelacion cooperativa antes del siguiente resultado."""


class Collector(Protocol):
    name: str
    version: str
    capabilities: CollectorCapabilities
    stats: dict[str, Any]

    def __enter__(self) -> "Collector":
        """Enter the collector context and return the resource used for search iteration."""
        ...
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Release collector resources on context exit, including when iteration raises an error."""
        ...
    def search(self, *, query: str, country: str, max_results: int,
               cancel_event: Event | None = None) -> Iterator[CollectedAd]:
        """Define cancellable iteration of normalized source ads up to the requested result budget."""
        ...
