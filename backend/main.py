import datetime
import webapp2
import logging
import urllib2
from google.appengine.api import mail
from google.appengine.ext import db, deferred
import json
import stripe
from google.appengine.api import memcache
import config_NOCOMMIT

# Test account secret key.
stripe.api_key = config_NOCOMMIT.STRIPE_SECRET_KEY

# This gets added to every pledge calculation
BASE_TOTAL = 38672900


class Pledge(db.Model):
  donationTime = db.DateTimeProperty(auto_now_add=True)
  fundraisingRound = db.StringProperty(required=True)

  email = db.EmailProperty(required=True)
  occupation = db.StringProperty(required=True)
  employer = db.StringProperty(required=True)
  phone = db.StringProperty()
  target = db.StringProperty()

  amountCents = db.IntegerProperty(required=True)
  stripeCustomer = db.StringProperty(required=True)

  note = db.TextProperty(required=False)


def send_thank_you(email, pledge_id, amount_cents):
  """ Deferred email task """

  sender = 'MayOne no-reply <noreply@mayday-pac.appspotmail.com>'
  subject = 'Thank you for your pledge'
  message = mail.EmailMessage(sender=sender, subject=subject)
  message.to = email


  format_kwargs = {
    # TODO: Use the person's actual name
    'name': email,
    # TODO: write a handler for this
    'tx_id': pledge_id,
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

    # NOTE: This line fails in dev_appserver due to SSL nonsense. It
    # seems to work in prod.
    customer = stripe.Customer.create(card=token)
    # customer = FakeCustomer()
    pledge = Pledge(email=email,
                    occupation=occupation,
                    employer=employer,
                    phone=phone,
                    target=target,
                    amountCents=amount,
                    stripeCustomer=customer.id,
                    note=self.request.get('note'),
                    fundraisingRound="1")
    pledge.save()

    # Add thank you email to a task queue
    deferred.defer(send_thank_you, email,
                   pledge.key().id(),
                   amount,
                   _queue="mail")

    self.response.write('Ok.')


app = webapp2.WSGIApplication([
  ('/total', GetTotalHandler),
  ('/pledge.do', PledgeHandler),
  ('/campaigns/may-one', EmbedHandler),
  ('/campaigns/may-one/', EmbedHandler)
], debug=True)
