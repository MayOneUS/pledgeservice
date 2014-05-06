import datetime
import json
import logging
import os
import urllib2
import webapp2

from google.appengine.api import mail, memcache
from google.appengine.ext import db, deferred

import model

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


app = webapp2.WSGIApplication([
  ('/admin/set_secrets', SetSecretsHandler),
], debug=False)
