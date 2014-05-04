import datetime
import json
import logging
import os
import urllib2
import webapp2

from google.appengine.api import mail, memcache
from google.appengine.ext import db, deferred

import stripe

import config_NOCOMMIT

stripe.api_key = config_NOCOMMIT.STRIPE_SECRET_KEY

# This gets added to every pledge calculation
BASE_TOTAL = 38672900


class User(db.Model):
  # a user's email is also the model key
  email = db.EmailProperty(required=True)

  # occupation and employer are logically required for all new users, but we
  # don't have this data for everyone. so from a data model perspective, they
  # aren't required.
  occupation = db.StringProperty(required=False)
  employer = db.StringProperty(required=False)

  phone = db.StringProperty(required=False)

  # whether or not the pledge was donated specifically for a particular
  # political affiliation
  target = db.StringProperty(required=False)

  # this is the nonce for what we'll put in a url to send to people when we ask
  # them to update their information. it's kind of like their password for the
  # user-management part of the site.
  url_nonce = db.StringProperty(required=True)

  @staticmethod
  @db.transactional
  def createOrUpdate(email, occupation=None, employer=None, phone=None,
                     target=None):
    user = User.get_by_key_name(email)
    if user is None:
      user = User(key_name=email,
                  email=email,
                  url_nonce=os.urandom(32).encode("hex"))
    user.occupation = occupation
    user.employer = employer
    user.phone = phone
    user.target = target
    user.put()
    return user


class Pledge(db.Model):
  # a user's email is also the User model key
  email = db.EmailProperty(required=True)

  # this is the string id for the stripe api to access the customer. we are
  # doing a whole stripe customer per pledge.
  stripeCustomer = db.StringProperty(required=True)

  # when the donation occurred
  donationTime = db.DateTimeProperty(auto_now_add=True)

  # we plan to have multiple fundraising rounds. right now we're in round "1"
  fundraisingRound = db.StringProperty(required=True)

  # what the user is pledging for
  amountCents = db.IntegerProperty(required=True)

  note = db.TextProperty(required=False)

  imported_wp_post_id = db.IntegerProperty(required=False)

  # it's possible we'll want to let people change just their pledge. i can't
  # imagine a bunch of people pledging with the same email address and then
  # getting access to change a bunch of other people's credit card info, but
  # maybe we should support users only changing information relating to a
  # specific pledge. if so, this is their site-management password.
  url_nonce = db.StringProperty(required=True)

  @staticmethod
  def create(email, stripe_customer_id, amount_cents, fundraisingRound="1",
             note=None):
    pledge = Pledge(email=email,
                    stripeCustomer=stripe_customer_id,
                    fundraisingRound=fundraisingRound,
                    amountCents=amount_cents,
                    note=note,
                    url_nonce=os.urandom(32).encode("hex"))
    pledge.put()
    return pledge

  @staticmethod
  @db.transactional
  def importOrUpdate(wp_post_id, email, stripe_customer_id, amount_cents,
                     fundraisingRound="1", note=None):
    pledges = Pledge.all().filter("imported_wp_post_id =", wp_post_id).run(
        limit=1)
    if not pledges:
        pledge = Pledge(url_nonce=os.urandom(32).encode("hex"),
                        imported_wp_post_id=wp_post_id)
    else:
        pledge = pledges[0]
    pledge.email = email
    pledge.stripeCustomer = stripe_customer_id
    pledge.fundraisingRound = fundraisingRound
    pledge.amountCents = amount_cents
    pledge.note = note
    pledge.put()
    return pledge


def addPledge(email, stripe_customer_id, amount_cents, occupation=None,
              employer=None, phone=None, fundraisingRound="1", target=None,
              note=None):
  """Creates a User model if one doesn't exist, finding one if one already
  does, using the email as a user key. Then adds a Pledge to the User with
  the given card token as a new credit card.

  @return: the pledge
  """
  # first, let's find the user by email
  User.createOrUpdate(
          email=email, occupation=occupation, employer=employer, phone=phone,
          target=target)

  return Pledge.create(
          email=email, stripe_customer_id=stripe_customer_id,
          amount_cents=amount_cents, fundraisingRound=fundraisingRound,
          note=note)


def importPledge(wp_post_id, email, stripe_customer_id, amount_cents,
                 occupation=None, employer=None, phone=None,
                 fundraisingRound="1", target=None, note=None):
  User.createOrUpdate(
          email=email, occupation=occupation, employer=employer, phone=phone,
          target=target)
  return Pledge.importOrUpdate(
          wp_post_id=wp_post_id, email=email,
          stripe_customer_id=stripe_customer_id, amount_cents=amount_cents,
          fundraisingRound=fundraisingRound, note=note)


def send_thank_you(email, url_nonce, amount_cents):
  """ Deferred email task """

  sender = 'MayOne no-reply <noreply@mayday-pac.appspotmail.com>'
  subject = 'Thank you for your pledge'
  message = mail.EmailMessage(sender=sender, subject=subject)
  message.to = email

  format_kwargs = {
    # TODO: Use the person's actual name
    'name': email,
    # TODO: write a handler for this
    'url_nonce': url_nonce,
    'total': '$%d' % int(amount_cents/100)
  }

  message.body = open('email/thank-you.txt').read().format(**format_kwargs)
  message.html = open('email/thank-you.html').read().format(**format_kwargs)
  message.send()


class GetTotalHandler(webapp2.RequestHandler):
  TOTAL_KEY = 'total'
  def get(self):
    data = memcache.get(GetTotalHandler.TOTAL_KEY)
    if data is not None:
      self.response.write(data)
      return
    logging.info('Total cache miss')
    total = BASE_TOTAL
    for pledge in Pledge.all():
      total += pledge.amountCents
    memcache.add(GetTotalHandler.TOTAL_KEY, total, 300)
    self.response.write(total)


class EmbedHandler(webapp2.RequestHandler):
  def get(self):
    if self.request.get("widget") == "1":
        self.redirect("/embed.html")
    else:
        self.redirect("/")


class FakeCustomer(object):
  def __init__(self):
    self.id = "1234"


class PledgeHandler(webapp2.RequestHandler):
  def post(self):
    try:
      data = json.loads(self.request.body)
    except:
      logging.Warning("Bad JSON request")
      self.error(400)
      self.response.write('Invalid request')
      return

    # ugh, consider using validictory?
    if ('email' not in data or
        'token' not in data or
        'amount' not in data or
        'userinfo' not in data or
        'occupation' not in data['userinfo'] or
        'employer' not in data['userinfo'] or
        'phone' not in data['userinfo'] or
        'target' not in data['userinfo']):
      self.error(400)
      self.response.write('Invalid request')
      return
    email = data['email']
    token = data['token']
    amount = data['amount']

    occupation = data['userinfo']['occupation']
    employer = data['userinfo']['employer']
    phone = data['userinfo']['phone']
    target = data['userinfo']['target']

    try:
      amount = int(amount)
    except ValueError:
      self.error(400)
      self.response.write('Invalid request')
      return

    if not (email and token and amount and occupation and employer and target):
      self.error(400)
      self.response.write('Invalid request: missing field')
      return

    if not mail.is_email_valid(email):
      self.error(400)
      self.response.write('Invalid request: Bad email address')
      return

    customer = stripe.Customer.create(card=token)

    pledge = addPledge(
            email=email, stripe_customer_id=customer.id, amount_cents=amount,
            occupation=occupation, employer=employer, phone=phone,
            target=target, note=self.request.get("note"))

    # Add thank you email to a task queue
    deferred.defer(send_thank_you, email, pledge.url_nonce, amount,
                   _queue="mail")

    self.response.write('Ok.')


app = webapp2.WSGIApplication([
  ('/total', GetTotalHandler),
  ('/pledge.do', PledgeHandler),
  ('/campaigns/may-one', EmbedHandler),
  ('/campaigns/may-one/', EmbedHandler)
], debug=False)
