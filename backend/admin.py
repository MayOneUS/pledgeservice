import calendar
import csv
import jinja2
import json
import logging
import os
import StringIO
import urllib2
import webapp2

from google.appengine.api import files, mail, memcache
from google.appengine.ext import blobstore, db, deferred
from google.appengine.ext.webapp import blobstore_handlers
from zipgun import Zipgun

import commands
import env
import model
import templates

class AdminDashboardHandler(webapp2.RequestHandler):
  def get(self):
    users = AdminDashboardHandler.get_missing_data_users()

    template = templates.GetTemplate('admin-dashboard.html')
    try:
      pledge_amounts = files.blobstore.get_file_name(
        blobstore.BlobInfo.all().filter(
          'filename =', 'pledge_amounts.csv'
        ).order('-creation').get().key())
    except:
      pledge_amounts = None
    try:
      pledges = files.blobstore.get_file_name(blobstore.BlobInfo.all().filter(
        'filename =', 'pledges.csv'
      ).order('-creation').get().key())
    except:
      pledges = None
    self.response.write(template.render({
      'missingUsers': [dict(email=user.email, amount=amt/100)
                       for user, amt in users],
      'totalMissing': sum(v for _, v in users)/100,
      'shardedCounterTotal': model.ShardedCounter.get_count('TOTAL-5'),
      'commands': AdminDashboardHandler.get_commands(),
      'pledge_amounts': pledge_amounts,
      'pledges': pledges
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
      if user.occupation and user.employer:
        db.delete(missing_user_secondary)
      else:
        # missing_user_secondary.amountCents never gets updated, but
        # that's okay, because it won't change unless the user makes a
        # new pledge, which will cause their info to be updated, so
        # we'll go down the other fork in this if.
        users.append((user, missing_user_secondary.amountCents))
    users.sort(key=lambda (_, amt): amt, reverse=True)
    return users

  @staticmethod
  def get_commands():
    return [dict(name=c.NAME, url='/admin/command/' + c.SHORT_NAME)
            for c in commands.COMMANDS if c.SHOW]


def generate_pledge_amounts_csv(file_name):
  """ Generates the pledge_amounts.csv file in a deferred way """

  csv_buffer = StringIO.StringIO()
  w = csv.writer(csv_buffer)
  w.writerow(['time', 'amount'])
  for pledge in model.WpPledge.all():
    w.writerow([str(pledge.donationTime), pledge.amountCents])
  for pledge in model.Pledge.all():
    w.writerow([str(pledge.donationTime), pledge.amountCents])
  with files.open(file_name, 'a') as f:
    f.write(csv_buffer.getvalue())
  csv_buffer.close()
  files.finalize(file_name)


class GeneratePledgeAmountsCsvHandler(webapp2.RequestHandler):
  def get(self):
    # Create a blobstore file, a deferred task, and redirect to the download
    # page.
    file_name = files.blobstore.create(
      mime_type='text/csv', _blobinfo_uploaded_filename="pledge_amounts.csv")
    deferred.defer(generate_pledge_amounts_csv, file_name, _queue='generateCSV')
    self.redirect('/admin/files%s/pledge_amounts.csv' % file_name)


def pledge_row(pledge, zg, full_data=False):
  try:
    user = model.User.all().filter('email =', pledge.email).get()
  except:
    logging.warning('No user found for pledge email: %s', pledge.email)
  zg_lookup = None
  if user.zipCode:
    zg_lookup = zg.lookup(user.zipCode)
  if not zg_lookup:
    zg_lookup = {'lat': '', 'lon': ''}

  if full_data:
    output = full_pledge_data(pledge,user)
  else:
    output = [
              user.zipCode,
              int(pledge.amountCents / 100.0),
              str(pledge.donationTime),
              pledge.donationTime.strftime('%-m/%-d/%y'),
              user.city,
              user.state,
              zg_lookup['lat'],
              zg_lookup['lon']
            ]
  return output

def full_pledge_data(pledge,user):
  if pledge.paypalPayerID:
    source = 'PAYPAL'
  elif pledge.bitpay_invoice_id:
    source = 'BITCOIN'
  else:
    source = 'STRIPE/MAYDAY.US'

  return [
    source,
    pledge.donationTime.strftime('%-m/%-d/%y'),
    pledge.amountCents/100.0,
    pledge.url_nonce,
    pledge.stripeCustomer or pledge.paypalPayerID or pledge.bitpay_invoice_id,
    pledge.email,
    user.first_name,
    user.last_name,
    user.address,
    '',
    user.city,
    user.state,
    user.zipCode,
    'United States',
    user.occupation,
    user.employer,
    user.target or 'Whatever Helps',
  ]



def generate_pledges_csv(file_name, pledge_type, pledge_time, full_data=False):
  """ Generates the pledges.csv file in a deferred way """

  PAGE_SIZE = 500
  csv_buffer = StringIO.StringIO()
  w = csv.writer(csv_buffer)
  if not pledge_time and pledge_type == 'WpPledge':
    # First time through, add the column headers
    if full_data:
      headers = ['SOURCE', 'donationTime', 'Amount ($)', 'url_nonce', 'stripeCustomer',
        'Email', 'First Name', 'Last Name', 'Address', 'Address 2', 'City', 'State',
        'Zip', 'Country', 'Occupation', 'Employer', 'Targeting']
    else:
      headers = ['zip', 'dollars', 'timestamp', 'date', 'city', 'state', 'latitude',
        'longitude']

    w.writerow(headers)
  zg = Zipgun('zipgun/zipcodes')

  # Get the next PAGE_SIZE pledges
  query = getattr(model, pledge_type).all().order('donationTime')
  if pledge_time:
    # Filter instead of using 'offset' because offset is very inefficient,
    # according to https://developers.google.com/appengine/articles/paging
    query = query.filter('donationTime >= ', pledge_time)
  pledges = query.fetch(PAGE_SIZE + 1)
  next_pledge_time = None
  if len(pledges) == PAGE_SIZE + 1:
    next_pledge_time = pledges[-1].donationTime
  pledges = pledges[:PAGE_SIZE]

  # Loop through the current pledges and write them to the csv
  for pledge in pledges:
    w.writerow(pledge_row(pledge, zg, full_data))
  with files.open(file_name, 'a') as f:
    f.write(csv_buffer.getvalue())
  csv_buffer.close()

  if not next_pledge_time and pledge_type == 'Pledge':
    # Last time through, finalize the file
    files.finalize(file_name)
  else:
    # More to process, recursively run again
    next_pledge_type = pledge_type
    if pledge_type == 'WpPledge' and not next_pledge_time:
      next_pledge_type = 'Pledge'
    deferred.defer(generate_pledges_csv, file_name, next_pledge_type,
                   next_pledge_time, full_data, _queue='generateCSV')


class GeneratePledgesCsvHandler(webapp2.RequestHandler):
  def get(self):
    # Create a blobstore file, a deferred task, and redirect to the download
    # page.
    file_name = files.blobstore.create(
      mime_type='text/csv', _blobinfo_uploaded_filename="pledges.csv")
    deferred.defer(generate_pledges_csv, file_name, 'WpPledge', None,
                   False, _queue='generateCSV')
    self.redirect('/admin/files%s/pledges.csv' % file_name)

class GeneratePledgesFullDataCsvHandler(webapp2.RequestHandler):
  def get(self):
    # Create a blobstore file, a deferred task, and redirect to the download
    # page.
    file_name = files.blobstore.create(
      mime_type='text/csv', _blobinfo_uploaded_filename="pledges_full_data.csv")
    deferred.defer(generate_pledges_csv, file_name, 'WpPledge', None,
                   True, _queue='generateCSV')
    self.redirect('/admin/files%s/pledges_full_data.csv' % file_name)


class CsvHandler(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, file_name):
    """
    Serve the blobstore file if it exists, otherwise instruct the user to
    refresh later.
    """
    try:
      blob_key = files.blobstore.get_blob_key(file_name)
      blob_info = blobstore.BlobInfo.get(blob_key)
      self.send_blob(blob_info)
    except:
      self.response.write('Working on it, refresh in a few minutes.')


class StretchHandler(webapp2.RequestHandler):
  def get(self):
    total = model.StretchCheckTotal.get()
    if total != 0:
      total = total/100
    template = templates.GetTemplate('stretch.html')
    self.response.write(template.render({'stretch': total}))

  def post(self):
    total = self.request.get("stretch")
    try:
      centsTotal = int(total) * 100
      model.StretchCheckTotal.update(centsTotal)

      # clear the cache so that it recalculates the next time
      model.ShardedCounter.clear('TOTAL-5')
      self.response.write('The Stretch total has been updated to: $' + str(total))
    except Exception as e:
      self.response.write('Sorry, something went wrong: ' + str(e))

def MakeCommandHandler(cmd_cls):
  """Takes a command class and returns a route tuple which allows that command
     to be executed.
  """
  class H(webapp2.RequestHandler):
    def get(self):
      self.response.write("""
      <h1>You are about to run command "{}". Are you sure?</h1>
      <form action="" method="POST">
      <button>Punch it</button>
      </form>""".format(self._get_cmd().NAME))

    def post(self):
      deferred.defer(self._get_cmd().run)
      self.response.write('Command started.')

    def _get_cmd(self):
      if 'cmds' not in self.app.registry:
        self.app.registry['cmds'] = {}
      if cmd_cls.SHORT_NAME not in self.app.registry['cmds']:
        self.app.registry['cmds'][cmd_cls.SHORT_NAME] = cmd_cls(self.app.config)
      return self.app.registry['cmds'][cmd_cls.SHORT_NAME]

  return ('/admin/command/' + cmd_cls.SHORT_NAME, H)


COMMAND_HANDLERS = [MakeCommandHandler(c) for c in commands.COMMANDS]

app = webapp2.WSGIApplication([
  ('/admin/generate/pledge_amounts.csv', GeneratePledgeAmountsCsvHandler),
  ('/admin/generate/pledges.csv', GeneratePledgesCsvHandler),
  ('/admin/generate/pledges_full_data.csv', GeneratePledgesFullDataCsvHandler),
  ('/admin/files(.+)/pledge_amounts.csv', CsvHandler),
  ('/admin/files(.+)/pledges.csv', CsvHandler),
  ('/admin/files(.+)/pledges_full_data.csv', CsvHandler),
  ('/admin/stretch', StretchHandler),
  ('/admin/?', AdminDashboardHandler),
] + COMMAND_HANDLERS, debug=False, config=dict(env=env.get_env()))
