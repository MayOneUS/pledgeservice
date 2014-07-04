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

def IncrementShardedCounterTotal(name, delta):
  memcache.incr(_COUNTER_TOTAL.format(name), delta)

def ClearShardedCounterTotal(name):
  memcache.delete(_COUNTER_TOTAL.format(name))
  

_TEAM_PLEDGES = 'TEAM-PLEDGES-{}'
def GetTeamPledgeCount(team):
  return memcache.get(_TEAM_PLEDGES.format(team))

def SetTeamPledgeCount(team, value):
  memcache.add(_TEAM_PLEDGES.format(team), value, 60)

def IncrementTeamPledgeCount(team, delta):
  memcache.incr(_TEAM_PLEDGES.format(team), delta)


_TEAM_TOTAL = 'TEAM-TOTAL-{}'
def GetTeamTotal(team):
  return memcache.get(_TEAM_TOTAL.format(team))

def SetTeamTotal(team, value):
  memcache.add(_TEAM_TOTAL.format(team), value, 60)

def IncrementTeamTotal(team, delta):
  memcache.incr(_TEAM_TOTAL.format(team), delta)
