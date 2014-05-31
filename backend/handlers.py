"""Handlers for MayOne.US."""

from collections import namedtuple
import datetime
import json
import logging
import cgi

from google.appengine.ext import db
from google.appengine.ext import deferred
import validictory
import webapp2

import model
import templates
import util

# Immutable environment with both configuration variables, and backends to be
# mocked out in tests.
Environment = namedtuple(
  'Environment',
  [
    # App engine app name, or 'local' for dev_appserver, or 'unittest' for unit
    # tests.
    'app_name',

    'stripe_public_key',

    # StripeBackend
    'stripe_backend',

    # MailingListSubscriber
    'mailing_list_subscriber',

    # MailSender
    'mail_sender',
  ])


class StripeBackend(object):
  """Interface which contacts stripe."""

  def CreateCustomer(self, email, card_token):
    """Creates a stripe customer so we can charge them later.

    Returns: A string customer id.
    """
    raise NotImplementedError()

  def Charge(self, customer_id, amount_cents):
    """Charges a customer and returns an identifier for the charge."""
    raise NotImplementedError()


class MailingListSubscriber(object):
  """Interface which signs folks up for emails."""
  def Subscribe(self, email, first_name, last_name, amount_cents, ip_addr, time,
                source):
    raise NotImplementedError()


class MailSender(object):
  """Interface which sends mail."""
  def Send(self, to, subject, text_body, html_body):
    raise NotImplementedError()


_STR = dict(type='string')
class PledgeHandler(webapp2.RequestHandler):
  """RESTful handler for pledge objects."""

  CREATE_SCHEMA = dict(
    type='object',
    properties=dict(
      email=_STR,
      phone=dict(type='string', blank=True),
      name=_STR,
      occupation=_STR,
      employer=_STR,
      target=_STR,
      subscribe=dict(type='boolean'),
      amountCents=dict(type='integer', minimum=100),
      team=dict(type='string', blank=True),

      payment=dict(type='object',
                   properties=dict(
                     STRIPE=dict(type='object',
                                 required=False,
                                 properties=dict(token=_STR)),
                     # TODO: Paypal
                   )
                 ),
    )
  )

  def post(self):
    """Create a new pledge, and update user info."""
    env = self.app.config['env']

    try:
      data = json.loads(self.request.body)
    except ValueError, e:
      logging.warning('Bad JSON request: %s', e)
      self.error(400)
      self.response.write('Invalid request')
      return

    try:
      validictory.validate(data, PledgeHandler.CREATE_SCHEMA)
    except ValueError, e:
      logging.warning('Schema check failed: %s', e)
      self.error(400)
      self.response.write('Invalid request')
      return

    # Do any server-side processing the payment processor needs.
    stripe_customer_id = None
    if 'STRIPE' in data['payment']:
      stripe_customer_id = env.stripe_backend.CreateCustomer(
        email=data['email'], card_token=data['payment']['STRIPE']['token'])
    else:
      logging.warning('No payment processor specified: %s', data)
      self.error(400)
      return

    # Split apart the name into first and last. Yes, this sucks, but adding the
    # name fields makes the form look way more daunting. We may reconsider this.
    # TODO: replace below with util.SplitName()
    name_parts = data['name'].split(None, 1)
    first_name = name_parts[0]
    if len(name_parts) == 1:
      last_name = ''
      logging.warning('Could not determine last name: %s', data['name'])
    else:
      last_name = name_parts[1]

    pledge = model.addPledge(email=data['email'],
                             stripe_customer_id=stripe_customer_id,
                             amount_cents=data['amountCents'],
                             first_name=first_name,
                             last_name=last_name,
                             occupation=data['occupation'],
                             employer=data['employer'],
                             phone=data['phone'],
                             target=data['target'],
                             team=data.get('team', ''),
                             mail_list_optin=data['subscribe'])

    if data['subscribe']:
      env.mailing_list_subscriber.Subscribe(
        email=data['email'],
        first_name=first_name, last_name=last_name,
        amount_cents=data['amountCents'],
        ip_addr=self.request.remote_addr,
        time=datetime.datetime.now(),
        source='pledged')

    # Add to the total asynchronously.
    deferred.defer(model.increment_donation_total, data['amountCents'],
                   _queue='incrementTotal')

    format_kwargs = {
      'name': data['name'].encode('utf-8'),
      'url_nonce': pledge.url_nonce,
      'total': '$%d' % int(data['amountCents'] / 100)
    }

    text_body = open('email/thank-you.txt').read().format(**format_kwargs)
    html_body = open('email/thank-you.html').read().format(**format_kwargs)

    env.mail_sender.Send(to=data['email'].encode('utf-8'),
                         subject='Thank you for your pledge',
                         text_body=text_body,
                         html_body=html_body)

    id = str(pledge.key())
    receipt_url = '/receipt/%s?auth_token=%s' % (id, pledge.url_nonce)

    self.response.headers['Content-Type'] = 'application/json'
    json.dump(dict(id=id,
                   auth_token=pledge.url_nonce,
                   receipt_url=receipt_url), self.response)

class SubscribeHandler(webapp2.RequestHandler):
  """RESTful handler for subscription requests."""
  # https://www.pivotaltracker.com/s/projects/1075614/stories/71725060

  def post(self):
    env = self.app.config['env']
    
    email = cgi.escape(self.request.get('email', default_value=None))
    if email is None:
      logging.warning("Bad Request: required field (email) missing.")
      self.error(400)
    
    name = cgi.escape(self.request.get('name', default_value=None))    
    #TODO: get zip 
    #TODO: get volunteer (YES/NO)
    #TODO: skills (up to 255)
    #TODO: rootstrikers (Waiting on details from Aaron re Mailchimp field update)
    
    # Split apart the name into first and last. Yes, this sucks, but adding the
    # name fields makes the form look way more daunting. We may reconsider this.
    first_name, last_name = util.SplitName(name)
    
    env.mailing_list_subscriber.Subscribe(
      email=email,
      first_name=first_name, last_name=last_name,
      amount_cents=0,
      ip_addr=self.request.remote_addr,
      time=datetime.datetime.now(),
      source='subscribed')

    self.redirect('/pledge')


class ReceiptHandler(webapp2.RequestHandler):
  def get(self, id):
    try:
      pledge = db.get(db.Key(id))
    except db.BadKeyError, e:
      logging.warning('Bad key error: %s', e)
      self.error(404)
      self.response.write('Not found')
      return

    if not pledge:
      self.error(404)
      self.response.write('Not found')
      return

    auth_token = self.request.get('auth_token')
    if not util.ConstantTimeIsEqual(auth_token, pledge.url_nonce):
      self.error(403)
      self.response.write('Access denied')
      return

    template = templates.GetTemplate('receipt.html')
    self.response.write(template.render(dict(pledge=pledge)))


class PaymentConfigHandler(webapp2.RequestHandler):
  def get(self):
    env = self.app.config['env']
    if not env.stripe_public_key:
      raise Error('No stripe public key in DB')
    params = dict(testMode=(env.app_name == u'local'),
                  stripePublicKey=env.stripe_public_key)

    self.response.headers['Content-Type'] = 'application/json'
    json.dump(params, self.response)


HANDLERS = [
  ('/r/pledge', PledgeHandler),
  ('/receipt/(.+)', ReceiptHandler),
  ('/r/payment_config', PaymentConfigHandler),
  ('/r/subscribe', SubscribeHandler),
]
