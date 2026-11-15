"""Adaptador de MetaAdsCollector; oculta sus modelos al consumidor."""

from importlib.metadata import version
from threading import Event
from typing import Iterator

from .base import (Advertiser, CollectedAd, CollectorCapabilities,
                   CollectorCancelled, CollectorError)


class MetaCollector:
    name = "meta_ad_library"
    capabilities = CollectorCapabilities(server_date_filter=True)

    def __init__(self, *, timeout: int = 20, max_retries: int = 1):
        from meta_ads_collector import MetaAdsCollector
        self.request_callback = None
        self.version = version("meta-ads-collector")
        self._backend = MetaAdsCollector(timeout=timeout, max_retries=max_retries)

    @property
    def stats(self):
        return self._backend.stats

    def __enter__(self):
        try:
            self._backend.__enter__()
        except Exception as exc:
            raise CollectorError(str(exc)) from exc
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._backend.__exit__(exc_type, exc_value, traceback)

    def search(self, *, query: str, country: str, max_results: int,
               cancel_event: Event | None = None, start_date=None, end_date=None) -> Iterator[CollectedAd]:
        if cancel_event is not None and cancel_event.is_set():
            raise CollectorCancelled("Consulta cancelada antes de iniciar")
        original_builder = None
        if start_date is not None:
            from .date_filter import install_date_filter
            original_builder = install_date_filter(self._backend.client,start_date,end_date,self.request_callback)
        try:
            for ad in self._backend.search(query=query, country=country,
                                           max_results=max_results):
                if cancel_event is not None and cancel_event.is_set():
                    raise CollectorCancelled("Consulta cancelada entre resultados")
                yield CollectedAd(
                    id=str(ad.id) if ad.id else "",
                    delivery_start_time=ad.delivery_start_time,
                    page=Advertiser(str(ad.page.id)) if ad.page and ad.page.id else None,
                    payload=ad.to_dict(),
                )
        except CollectorError:
            raise
        except Exception as exc:
            raise CollectorError(str(exc)) from exc
        finally:
            if original_builder is not None:
                self._backend.client._build_graphql_payload = original_builder
