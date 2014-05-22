"""One-off commands only accessible to admins."""

import logging

from collections import defaultdict

from google.appengine.ext import db

import model


class Error(Exception): pass


# Format for a command. SHORT_NAME should be URL-safe. You can execute
# the command by going to "/admin/command/$SHORT_NAME".
#
# Commands are, by default, run in a task queue, so they have a 10
# minute deadline. Make it count, or if it takes longer than that, use
# deferred chaining by catching DeadlineExceededError and deferring a
# call to yourself which picks up where you left off.
class TestCommand(object):
  SHORT_NAME = 'test'
  NAME = 'Perform a test'
  SHOW = False

  def run(self):
    logging.info('Do something')


# Populates the MissingDataUsersSecondary table.
class FindMissingDataUsersCommand(object):
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
             if not (u.occupation and u.employer and u.target)]

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


class UpdateSecretsProperties(object):
  SHORT_NAME = 'update_secrets_properties'
  NAME = 'Update "Secrets" model properties'
  SHOW = True

  def run(self):
    model.Secrets.update()


# List your command here so admin.py can expose it.
COMMANDS = [
  TestCommand(),
  FindMissingDataUsersCommand(),
  UpdateSecretsProperties(),
]
