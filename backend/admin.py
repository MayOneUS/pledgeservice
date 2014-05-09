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
  MISSING_DATA_USERS_KEY = 'MISSING_DATA_USERS'

  def get(self):
    users = AdminDashboardHandler.get_missing_data_users()
    template = JINJA_ENVIRONMENT.get_template('admin-dashboard.html')
    self.response.write(template.render({
      'missingUsers': [dict(email=user.email, amount=amt/100)
                       for user, amt in users],
      'totalMissing': sum(v for _, v in users)/100,
    }))

  # Gets all the users with missing employer/occupation data who gave at least
  # $200 when we were on wordpress. Caches the result. Since the list can only
  # shrink over time, there's no need to expire the memcache entry, and we pare
  # it down on each request.
  @staticmethod
  def get_missing_data_users():
    users = []
    for user in AdminDashboardHandler._coarse_missing_data_users():
      if user.occupation and user.employer:
        continue
      pledges = (db.Query(model.WpPledge, projection=('amountCents',))
                 .filter('email =', user.email))
      total = sum(p.amountCents for p in pledges)
      if total >= 20000:
        users.append((user, total))
    memcache.set(AdminDashboardHandler.MISSING_DATA_USERS_KEY,
                 [user.key() for user, _ in users])
    return users

  # Returns a generator for a coarse list of users such that all users with
  # missing data who gave at least $200 will be on it. It's either based on the
  # list of such users last time we did this query (if it's still in memcache),
  # or it's simply all users, if that has expired.
  @staticmethod
  def _coarse_missing_data_users():
    keys = memcache.get(AdminDashboardHandler.MISSING_DATA_USERS_KEY)
    if keys:
      return db.get(keys)
    else:
      return model.User.all()


class PledgesCsvHandler(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Content-type'] = 'text/csv'
    w = csv.writer(self.response)
    w.writerow(['time', 'amount'])
    for pledge in model.WpPledge.all():
      w.writerow([str(pledge.donationTime), pledge.amountCents])
    for pledge in model.Pledge.all():
      w.writerow([str(pledge.donationTime), pledge.amountCents])


app = webapp2.WSGIApplication([
  ('/admin/set_secrets', SetSecretsHandler),
  ('/admin/pledges.csv', PledgesCsvHandler),
  ('/admin/?', AdminDashboardHandler),
], debug=False)
