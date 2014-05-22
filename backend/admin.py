import calendar
import csv
import jinja2
import json
import logging
import os
import urllib2
import webapp2

from google.appengine.api import mail, memcache
from google.appengine.ext import db, deferred

import commands
import model

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates/'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class SetSecretsHandler(webapp2.RequestHandler):
  def get(self):
    s = model.Secrets.get()
    if s:
      self.response.write('Secrets already set. Delete them before reseting')
      return

    self.response.write("""
    <form method="post" action="">
      <label>Stripe public key</label>
      <input name="stripe_public_key">
      <label>Stripe private key</label>
      <input name="stripe_private_key">
      <input type="submit">
    </form>""")

  def post(self):
    model.Secrets.update(
      stripe_public_key=self.request.get('stripe_public_key'),
      stripe_private_key=self.request.get('stripe_private_key'))


class AdminDashboardHandler(webapp2.RequestHandler):
  def get(self):
    users = AdminDashboardHandler.get_missing_data_users()

    pre_sharding_total = 0
    post_sharding_total = 0
    for p in model.Pledge.all():
      if p.model_version >= 2:
        post_sharding_total += p.amountCents
      else:
        pre_sharding_total += p.amountCents

    template = JINJA_ENVIRONMENT.get_template('admin-dashboard.html')
    self.response.write(template.render({
      'missingUsers': [dict(email=user.email, amount=amt/100)
                       for user, amt in users],
      'totalMissing': sum(v for _, v in users)/100,
      'preShardedTotal': pre_sharding_total,
      'postShardedTotal': post_sharding_total,
      'shardedCounterTotal': model.ShardedCounter.get_count('TOTAL'),
    }))

  # Gets all the users with missing employer/occupation/targeting data
  # who gave at least $200 when we were on wordpress. If a user has
  # since updated their info, delete that user's record in the
  # MissingDataUsersSecondary model.
  #
  # Returns list of (User, amountCents) tuples.
  @staticmethod
  def get_missing_data_users():
    users = []
    for missing_user_secondary in model.MissingDataUsersSecondary.all():
      user = model.User.get_by_key_name(missing_user_secondary.email)

      # If they've added their info, delete them.
      if user.occupation and user.employer and user.target:
        db.delete(missing_user_secondary)
      else:
        # missing_user_secondary.amountCents never gets updated, but
        # that's okay, because it won't change unless the user makes a
        # new pledge, which will cause their info to be updated, so
        # we'll go down the other fork in this if.
        users.append((user, missing_user_secondary.amountCents))

    return users


class PledgesCsvHandler(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Content-type'] = 'text/csv'
    w = csv.writer(self.response)
    w.writerow(['time', 'amount'])
    for pledge in model.WpPledge.all():
      w.writerow([str(pledge.donationTime), pledge.amountCents])
    for pledge in model.Pledge.all():
      w.writerow([str(pledge.donationTime), pledge.amountCents])


def MakeCommandHandler(cmd):
  """Takes a command and returns a route tuple which allows that command
     to be executed.
  """
  class H(webapp2.RequestHandler):
    def get(self):
      self.response.write("""
      <h1>You are about to run command "{}". Are you sure?</h1>
      <form action="" method="POST">
      <button>Punch it</button>
      </form>""".format(cmd.NAME))

    def post(self):
      deferred.defer(cmd.run)
      self.response.write('Command started.')

  return ('/admin/command/' + cmd.SHORT_NAME, H)


COMMAND_HANDLERS = [MakeCommandHandler(c) for c in commands.COMMANDS]

app = webapp2.WSGIApplication([
  ('/admin/set_secrets', SetSecretsHandler),
  ('/admin/pledges.csv', PledgesCsvHandler),
  ('/admin/?', AdminDashboardHandler),
] + COMMAND_HANDLERS, debug=False)
