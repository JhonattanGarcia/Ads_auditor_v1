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
        """Initialize the provider adapter and network client without running a search."""
        from meta_ads_collector import MetaAdsCollector
        self.request_callback = None
        self.version = version("meta-ads-collector")
        self._backend = MetaAdsCollector(timeout=timeout, max_retries=max_retries)

    @property
    def stats(self):
        """Expose provider collection counters without copying or altering them."""
        return self._backend.stats

    def __enter__(self):
        """Enter the collector context and return the resource used for search iteration."""
        try:
            self._backend.__enter__()
        except Exception as exc:
            raise CollectorError(str(exc)) from exc
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Release collector resources on context exit, including when iteration raises an error."""
        self._backend.__exit__(exc_type, exc_value, traceback)

    def search(self, *, query: str, country: str, max_results: int,
               cancel_event: Event | None = None, start_date=None, end_date=None) -> Iterator[CollectedAd]:
        """Yield normalized provider ads while enforcing optional page budgets and restoring temporary client hooks."""
        if cancel_event is not None and cancel_event.is_set():
            raise CollectorCancelled("Consulta cancelada antes de iniciar")
        original_page_search=None
        if getattr(self,'max_pages',None) is not None:
            original_page_search=self._backend.client.search_ads
            def limited_page(**kwargs):
                """Stop pagination at the configured page budget without fetching an additional page."""
                if self._backend.stats.get('pages_fetched',0)>=self.max_pages:
                    self._backend.stats['page_limit_reached']=True
                    return {'ads':[]},None
                response,cursor=original_page_search(**kwargs)
                if cursor and self._backend.stats.get('pages_fetched',0)+1>=self.max_pages:
                    self._backend.stats['page_limit_reached']=True
                    cursor=None
                if getattr(self,'page_callback',None):
                    self.page_callback({'pages_fetched':self._backend.stats.get('pages_fetched',0)+1,'page_limit_reached':self._backend.stats.get('page_limit_reached',False)})
                return response,cursor
            self._backend.client.search_ads=limited_page
        original_builder = None
        try:
            if start_date is not None:
                from .date_filter import install_date_filter
                original_builder = install_date_filter(self._backend.client,start_date,end_date,self.request_callback)
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
            if original_page_search is not None:
                self._backend.client.search_ads=original_page_search
            if original_builder is not None:
                self._backend.client._build_graphql_payload = original_builder
