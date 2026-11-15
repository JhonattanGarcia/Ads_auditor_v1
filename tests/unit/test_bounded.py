import threading
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
import json

from brand_threat_monitor.collectors.base import Advertiser, CollectedAd, CollectorCancelled, CollectorError
from brand_threat_monitor.collectors.bounded import BoundedMetaCollector, CollectorTimeout
from brand_threat_monitor.ingestion.collector import collect


def one_ad_then_stall(sender,*args):
    sender.send(('ad',CollectedAd('synthetic',datetime.now(timezone.utc),Advertiser('page'),{})))
    time.sleep(30)


def no_response(sender,*args):
    time.sleep(30)


def finished(sender,*args):
    sender.send(('done',{'ads_collected':0,'errors':0}))
    sender.close()


class BoundedTests(unittest.TestCase):
    def test_idle_timeout_keeps_received_result(self):
        profile=json.loads((Path(__file__).resolve().parents[2]/'profiles/example.json').read_text(encoding='utf-8-sig'))
        factory=lambda **kwargs:BoundedMetaCollector(**kwargs,idle_timeout=1.5,max_duration=5,worker_target=one_ad_then_stall)
        started=time.monotonic()
        result=collect(profile,collector_factory=factory)
        self.assertEqual(result['ads'][0]['ad_id'],'synthetic')
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['errors'][0]['type'],'CollectorTimeout')
        self.assertLess(time.monotonic()-started,8)

    def test_total_timeout_terminates_waiting_process(self):
        collector=BoundedMetaCollector(max_duration=1,idle_timeout=10,worker_target=no_response)
        with collector:
            with self.assertRaises(CollectorTimeout):
                list(collector.search(query='test',country='CO',max_results=10))
        self.assertIsNone(collector.process)

    def test_cancel_interrupts_wait_without_waiting_for_network(self):
        event=threading.Event()
        timer=threading.Timer(0.5,event.set); timer.start()
        collector=BoundedMetaCollector(worker_target=no_response)
        try:
            with collector:
                with self.assertRaises(CollectorCancelled):
                    list(collector.search(query='test',country='CO',max_results=10,cancel_event=event))
        finally: timer.cancel()
        self.assertIsNone(collector.process)

    def test_empty_completed_search_is_not_a_timeout(self):
        with BoundedMetaCollector(worker_target=finished) as collector:
            self.assertEqual(list(collector.search(query='test',country='CO',max_results=10)),[])


if __name__=='__main__': unittest.main()
