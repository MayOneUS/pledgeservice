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
import env
import model
import templates

class AdminDashboardHandler(webapp2.RequestHandler):
  def get(self):
    users = AdminDashboardHandler.get_missing_data_users()

    pre_sharding_total = 0
    post_sharding_total = 0
    for p in model.Pledge.all():
      if p.model_version >= 5:
        post_sharding_total += p.amountCents
      else:
        pre_sharding_total += p.amountCents

    template = templates.GetTemplate('admin-dashboard.html')
    self.response.write(template.render({
      'missingUsers': [dict(email=user.email, amount=amt/100)
                       for user, amt in users],
      'totalMissing': sum(v for _, v in users)/100,
      'preShardedTotal': pre_sharding_total,
      'postShardedTotal': post_sharding_total,
      'shardedCounterTotal': model.ShardedCounter.get_count('TOTAL-5'),
      'commands': AdminDashboardHandler.get_commands(),
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


class PledgesCsvHandler(webapp2.RequestHandler):
  def get(self):
    self.response.headers['Content-type'] = 'text/csv'
    w = csv.writer(self.response)
    w.writerow(['time', 'amount'])
    for pledge in model.WpPledge.all():
      w.writerow([str(pledge.donationTime), pledge.amountCents])
    for pledge in model.Pledge.all():
      w.writerow([str(pledge.donationTime), pledge.amountCents])


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
  ('/admin/pledges.csv', PledgesCsvHandler),
  ('/admin/stretch', StretchHandler),
  ('/admin/?', AdminDashboardHandler),
] + COMMAND_HANDLERS, debug=False, config=dict(env=env.get_env()))
