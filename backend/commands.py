"""One-off commands only accessible to admins."""

import logging

from collections import defaultdict

from google.appengine.ext import db
from google.appengine.ext import deferred

import model
import cache


class Error(Exception): pass

class Command(object):
  """Base class for commands."""
  def __init__(self, config):
    self.config = config


# Format for a command. SHORT_NAME should be URL-safe. You can execute
# the command by going to "/admin/command/$SHORT_NAME".
#
# Commands are, by default, run in a task queue, so they have a 10
# minute deadline. Make it count, or if it takes longer than that, use
# deferred chaining by catching DeadlineExceededError and deferring a
# call to yourself which picks up where you left off.
class TestCommand(Command):
  SHORT_NAME = 'test'
  NAME = 'Perform a test'
  SHOW = False

  def run(self):
    logging.info('Do something')


# Populates the MissingDataUsersSecondary table.
class FindMissingDataUsersCommand(Command):
  SHORT_NAME = 'find_missing_data_users'
  NAME = 'Recompute missing data users'
  SHOW = False

  def run(self):
    if model.MissingDataUsersSecondary.all().count() > 0:
      raise Error('Must clear MissingDataUsersSecondary before refreshing')

    # Load the whole data model. As of 2014-05-20, this takes around
    # 30 seconds, out of our allotted 10 minutes.
    logging.info('Load all users')
    users = [u.email for u in model.User.all()
             if not (u.occupation and u.employer)]

    logging.info('Load all Pledges')
    pledges = list(model.Pledge.all())
    logging.info('Load all WpPledges')
    wp_pledges = list(model.WpPledge.all())
    logging.info('Done loading')

    pledge_sum = defaultdict(int)
    for p in pledges + wp_pledges:
      pledge_sum[p.email] += p.amountCents

    users = [u for u in users if pledge_sum[u] >= 20000]
    users = [model.MissingDataUsersSecondary(email=u, amountCents=pledge_sum[u])
             for u in users]
    db.put(users)
    logging.info('Done')


class UpdateSecretsProperties(Command):
  SHORT_NAME = 'update_secrets_properties'
  NAME = 'Update "Secrets" model properties'
  SHOW = True

  def run(self):
    model.Secrets.update()


class ChargeRequested(Command):
  SHORT_NAME = 'execute_requested_charges'
  NAME = 'Execute requested charges'
  SHOW = True

  def run(self):
    for charge_status in model.ChargeStatus.all().filter('start_time =', None):
      deferred.defer(self.charge_one,
                     charge_status.key().parent(),
                     _queue='stripeCharge')

  def charge_one(self, pledge_key):
    model.ChargeStatus.execute(self.config['env'].stripe_backend, pledge_key)


class RequestAllPledges(Command):
  SHORT_NAME = 'request_all_pledges'
  NAME = 'Request charges for all pledges'
  SHOW = True

  def run(self):
    logging.info('Start')
    pledge_keys = set(str(k) for k in model.Pledge.all(keys_only=True))
    requested_keys = set(str(k.parent())
                         for k in model.ChargeStatus.all(keys_only=True))
    needed_keys = pledge_keys.difference(requested_keys)
    logging.info('Loaded')
    for pledge_key in needed_keys:
      model.ChargeStatus.request(db.Key(pledge_key))
    logging.info('Done')


class BackfillTeamTotalNumPledges(Command):
  SHORT_NAME = 'backfill_teamtotal_num_pledges'
  NAME = 'backfill TeamTotal.num_pledges'
  SHOW = True

  def run(self):
    for tt in model.TeamTotal.all():
      if not tt.num_pledges:
        tt.num_pledges = 0
      tt.num_pledges += model.Pledge.all().filter("model_version <=", 11).filter(
        "team =", tt.team).count()
      tt.put()


class BackfillTeamTotalNumPledges(Command):
  SHORT_NAME = 'backfill_teamtotal_num_pledges'
  NAME = 'backfill TeamTotal.num_pledges'
  SHOW = True

  def run(self):
    for tt in model.TeamTotal.all():
      if not tt.num_pledges:
        tt.num_pledges = 0
      tt.num_pledges += model.Pledge.all().filter("model_version <=", 11).filter(
        "team =", tt.team).count()
      tt.put()


class ResetTeamPledgeCount(Command):
  SHORT_NAME = 'reset_team_num_pledges'
  NAME = 'reset the TeamTotal.num_pledges counter from memcache'
  SHOW = True

  def run(self):
    for tt in model.TeamTotal.all():
      team_pledges = cache.GetTeamPledgeCount(tt.team) or 0
      if team_pledges != tt.num_pledges:
        tt.num_pledges = team_pledges
        tt.put()


# List your command here so admin.py can expose it.
COMMANDS = [
  ResetTeamPledgeCount,
  BackfillTeamTotalNumPledges,
  TestCommand,
  FindMissingDataUsersCommand,
  UpdateSecretsProperties,
  RequestAllPledges,
  ChargeRequested,
]
