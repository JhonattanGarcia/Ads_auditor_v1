"""Fuente ficticia reproducible para pruebas sin red."""

import json
from datetime import datetime
from pathlib import Path
from threading import Event

from .base import (Advertiser, CollectedAd, CollectorCapabilities,
                   CollectorCancelled, CollectorError)


class FixtureCollector:
    name = "fixture"
    version = "1.0"
    capabilities = CollectorCapabilities(pagination=False)

    def __init__(self, path: Path, *, fail_after: int | None = None):
        """Initialize a deterministic offline collector with scripted records and failure behavior."""
        self.path = path
        self.fail_after = fail_after
        self.stats = {"errors": 0}

    def __enter__(self):
        """Enter the collector context and return the resource used for search iteration."""
        return self

    def __exit__(self, *args):
        """Release collector resources on context exit, including when iteration raises an error."""
        pass

    def search(self, *, query, country, max_results, cancel_event: Event | None = None):
        """Yield deterministic offline ads and simulate configured source errors or cancellation."""
        records = json.loads(self.path.read_text(encoding="utf-8"))["ads"]
        emitted = 0
        for record in records:
            if cancel_event is not None and cancel_event.is_set():
                raise CollectorCancelled("Consulta ficticia cancelada")
            if emitted >= max_results:
                return
            if self.fail_after is not None and emitted >= self.fail_after:
                self.stats["errors"] += 1
                raise CollectorError("Fallo de paginacion simulado")
            if record["country"] != country or query.casefold() not in record["body"].casefold():
                continue
            stamp = record.get("delivery_start_time")
            advertiser = record.get("advertiser_id")
            yield CollectedAd(record["ad_id"], datetime.fromisoformat(stamp) if stamp else None,
                              Advertiser(advertiser) if advertiser else None, record)
            emitted += 1
