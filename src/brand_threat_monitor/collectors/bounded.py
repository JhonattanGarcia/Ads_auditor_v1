"""Ejecuta el proveedor en un proceso terminable con limites de espera reales."""

import multiprocessing as mp
import time
from importlib.metadata import version

from .base import CollectorCapabilities, CollectorCancelled, CollectorError


class CollectorTimeout(CollectorError):
    pass


def meta_worker(sender, query, country, max_results, timeout, max_retries, start_date=None, end_date=None):
    """Solo este proceso toca el cliente de red del proveedor."""
    from .meta import MetaCollector
    try:
        with MetaCollector(timeout=timeout,max_retries=max_retries) as collector:
            collector.request_callback=lambda info:sender.send(('request',info))
            for ad in collector.search(query=query,country=country,max_results=max_results,
                                       start_date=start_date,end_date=end_date):
                sender.send(('ad',ad))
            sender.send(('done',dict(collector.stats)))
    except Exception as exc:
        sender.send(('error',{'type':type(exc).__name__,'message':str(exc)}))
    finally:
        sender.close()


class BoundedMetaCollector:
    name='meta_ad_library'
    capabilities=CollectorCapabilities(server_date_filter=True,cancellation='process_termination')

    def __init__(self, *, timeout=20, max_retries=1, max_duration=120,
                 idle_timeout=45, worker_target=meta_worker):
        self.version=version('meta-ads-collector')
        self.timeout=timeout
        self.max_retries=max_retries
        self.max_duration=max_duration
        self.idle_timeout=idle_timeout
        self.worker_target=worker_target
        self.progress_callback=None
        self.stats={'errors':0,'ads_collected':0,'date_filter_requests':[]}
        self.process=None
        self.receiver=None

    def __enter__(self): return self

    def __exit__(self,*args):
        self.cleanup()

    def cleanup(self):
        if self.process is not None:
            if self.process.is_alive(): self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill(); self.process.join(timeout=2)
            self.process.close(); self.process=None
        if self.receiver is not None:
            self.receiver.close(); self.receiver=None

    def search(self, *, query, country, max_results, cancel_event=None, start_date=None, end_date=None):
        if cancel_event is not None and cancel_event.is_set():
            raise CollectorCancelled('Search cancelled before starting')
        context=mp.get_context('spawn')
        self.receiver,sender=context.Pipe(duplex=False)
        self.process=context.Process(target=self.worker_target,args=(sender,query,country,max_results,self.timeout,self.max_retries,start_date,end_date),daemon=True)
        started=last_result=last_progress=time.monotonic()
        try:
            self.process.start(); sender.close()
            while True:
                now=time.monotonic()
                if cancel_event is not None and cancel_event.is_set():
                    raise CollectorCancelled('Search stopped by the user')
                if now-started>=self.max_duration:
                    raise CollectorTimeout(f'Search exceeded {self.max_duration}s total; received results were preserved')
                if now-last_result>=self.idle_timeout:
                    raise CollectorTimeout(f'No ads received for {self.idle_timeout}s; source may be retrying or returning empty pages')
                if self.progress_callback and now-last_progress>=2:
                    self.progress_callback({'elapsed_seconds':int(now-started),'received_ads':self.stats['ads_collected'],
                                            'message':'Waiting for Meta or the next page'})
                    last_progress=now
                if not self.receiver.poll(0.1):
                    if not self.process.is_alive():
                        raise CollectorError('Collector process ended without a completion message')
                    continue
                try: kind,value=self.receiver.recv()
                except EOFError as exc:
                    raise CollectorError('Collector connection closed before completion') from exc
                if kind=='ad':
                    last_result=time.monotonic()
                    self.stats['ads_collected']+=1
                    if self.progress_callback:
                        self.progress_callback({'elapsed_seconds':int(last_result-started),'received_ads':self.stats['ads_collected'],
                                                'message':'Inspecting received ads'})
                    yield value
                elif kind=='request':
                    self.stats['date_filter_requests'].append(value)
                elif kind=='done':
                    self.stats.update(value)
                    return
                elif kind=='error':
                    self.stats['errors']+=1
                    raise CollectorError(f"{value['type']}: {value['message']}")
                else: raise CollectorError('Unexpected collector process message')
        finally:
            sender.close()
            self.cleanup()
