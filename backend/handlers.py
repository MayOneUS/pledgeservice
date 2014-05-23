"""Handlers for MayOne.US."""

from collections import namedtuple
import json
import logging
import webapp2

import validictory

# Immutable environment with both configuration variables, and backends to be
# mocked out in tests.
Environment = namedtuple(
  'Environment',
  [
    # AppEngine app name.
    'app_name',

    # Stripe creds to export.
    'stripe_public_key',

    # PaymentProcessor
    'payment_processor',

    # MailingListSubscriber
    'mailing_list_subscriber',
  ])


class PaymentProcessor(object):
  """Interface which processes payments."""
  def CreateCustomer(self, payment_params, pledge_model):
    """Does whatever the payment processor needs to do in order to be able to
    charge the customer later.

    Args:
      payment_params: dict with keys like 'paypal' or 'stripe', with values
          which are dicts with parameters specific to that payment platform.
      pledge_model: A not-yet-committed pledge model for us to modify to include
          a record of the customer.
    """
    raise NotImplementedError()


class MailingListSubscriber(object):
  """Interface which signs folks up for emails."""
  def Subscribe(self, first_name, last_name, amount_cents, ip_addr, time,
                source):
    raise NotImplementedError()


_STR = dict(type='string')
class PledgeHandler(webapp2.RequestHandler):
  CREATE_SCHEMA = dict(
    type='object',
    properties=dict(
      email=_STR,
      phone=dict(type='string', blank=True),
      firstName=_STR,
      lastName=_STR,
      occupation=_STR,
      employer=_STR,
      target=_STR,
      subscribe=dict(type='boolean'),
      amountCents=dict(type='integer', minimum=100)
    )
  )

  def post(self):
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

    self.response.headers['Content-Type'] = 'application/json'
    json.dump(dict(id='2'), self.response)


HANDLERS = [
  ('/r/pledge', PledgeHandler),
]
