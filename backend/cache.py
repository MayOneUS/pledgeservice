"""Helpers for storing and retriving data from memcache."""

import logging

from google.appengine.api import memcache


_COUNTER_TOTAL = 'COUNTER-TOTAL-{}'
def GetShardedCounterTotal(name):
  res = memcache.get(_COUNTER_TOTAL.format(name))
  if not res:
    logging.info('Cache miss: Shared counter %s', name)
  return res

def SetShardedCounterTotal(name, value):
  memcache.add(_COUNTER_TOTAL.format(name), value, 60)
