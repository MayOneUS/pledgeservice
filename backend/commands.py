"""One-off commands only accessible to admins."""

import logging
import paypal

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
        tt.put()
      elif tt.num_pledges == 0:
        tt.num_pledges += model.Pledge.all().filter("team =", tt.team).count()
        tt.put()
      else:
        logging.info('Ignoring %s because it has %d already' % (tt.team, tt.num_pledges))

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


def update_user_data(env, pledge_type, pledge_time):
  """ Use a deferred task to batch update stripe user data """

  PAGE_SIZE = 500

  # Get the next PAGE_SIZE pledges
  query = getattr(model, pledge_type).all().order('-donationTime')
  if pledge_time:
    # Filter instead of using 'offset' because offset is very inefficient,
    # according to https://developers.google.com/appengine/articles/paging
    query = query.filter('donationTime <= ', pledge_time)
  pledges = query.fetch(PAGE_SIZE + 1)
  next_pledge_time = None
  if len(pledges) == PAGE_SIZE + 1:
    next_pledge_time = pledges[-1].donationTime
  pledges = pledges[:PAGE_SIZE]

  # Loop through the current pledges and update the associated user with data
  # pulled from Stripe or Paypal
  for pledge in pledges:
    try:
      user = model.User.all().filter('email =', pledge.email).get()
      if user.zipCode and user.address and user.address != 'None':
        continue
      if hasattr(pledge, 'paypalTransactionID') and pledge.paypalTransactionID:
        request_data = {
          'METHOD': 'GetTransactionDetails',
          'TRANSACTIONID': pledge.paypalTransactionID
        }
        rc, txn_data = paypal.send_request(request_data)
        if not rc:
          logging.warning('Error retrieving PayPal transaction: %s', txn_data)
          continue
        user.zipCode = txn_data['SHIPTOZIP'][0]
        user.address = txn_data['SHIPTOSTREET'][0]
        if 'SHIPTOSTREET2' in txn_data:
          user.address += ', %s' % txn_data['SHIPTOSTREET2'][0]
        user.city = txn_data['SHIPTOCITY'][0]
        user.state = txn_data['SHIPTOSTATE'][0]
      elif pledge.stripeCustomer:
        card_data = env.stripe_backend.RetrieveCardData(pledge.stripeCustomer)
        user.zipCode = card_data['address_zip']
        address = card_data['address_line1']
        if card_data['address_line2']:
          address += ', %s' % card_data['address_line2']
        user.address = address
        user.city = card_data['address_city']
        user.state = card_data['address_state']
      user.put()
    except Exception, e:
      logging.warning('Error updating user %s with error, %s', user.email, e)

  if next_pledge_time or pledge_type == 'WpPledge':
    # More to process, recursively run again
    next_pledge_type = pledge_type
    if pledge_type == 'WpPledge' and not next_pledge_time:
      next_pledge_type = 'Pledge'
    deferred.defer(update_user_data, env, next_pledge_type, next_pledge_time)


class UpdateUserData(Command):
  SHORT_NAME = 'update_user_data'
  NAME = 'Fill in missing user address data from Stripe and PayPal'
  SHOW = True

  def run(self):
    deferred.defer(update_user_data, self.config['env'], 'WpPledge', None)


# List your command here so admin.py can expose it.
COMMANDS = [
  ResetTeamPledgeCount,
  BackfillTeamTotalNumPledges,
  TestCommand,
  FindMissingDataUsersCommand,
  UpdateSecretsProperties,
  RequestAllPledges,
  ChargeRequested,
  UpdateUserData
]
