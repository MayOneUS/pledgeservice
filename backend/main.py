#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import datetime
import webapp2
import logging
import urllib2
from google.appengine.api import mail
from google.appengine.ext import db, deferred
import json
import stripe
from google.appengine.api import memcache


# Test account secret key.
stripe.api_key = "sk_test_W9JDlj3jnfWkaEg8OHpVjVcX"


class Pledge(db.Model):
  donationTime = db.DateTimeProperty(auto_now_add=True)
  fundraisingRound = db.StringProperty(required=True)

  email = db.EmailProperty(required=True)
  occupation = db.StringProperty(required=True)
  employer = db.StringProperty(required=True)

  amountCents = db.IntegerProperty(required=True)
  stripeCustomer = db.StringProperty(required=True)

  note = db.TextProperty(required=False)


class MainHandler(webapp2.RequestHandler):
  def get(self):
    self.response.write('Hello world!')


def send_thank_you(email, pledge_id):
  """ Deferred email task """

  sender = 'MayOne no-reply <noreply@pure-spring-568.appspotmail.com>'
  subject = 'Thank you for your pledge'
  message = mail.EmailMessage(sender=sender, subject=subject)
  message.to = email
  format_kwargs = {
    'name': email,
    # TODO: Softcode the receipt link
    'receipt_link': 'http://localhost:8080/pledge/%s' % pledge_id
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

    total = 0
    for pledge in Pledge.all():
      total += pledge.amountCents
    memcache.add(GetTotalHandler.TOTAL_KEY, total, 60)
    self.response.write(total)


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
    email = data.get('email')
    occupation = data.get('occupation')
    employer = data.get('employer')
    token = data.get('token')

    try:
      amount = int(data.get('amount', '0'))
    except ValueError:
      self.error(400)
      self.response.write('Invalid request')
      return

    if not (email and occupation and employer and token and amount):
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
                    amountCents=amount,
                    stripeCustomer=customer.id,
                    note=self.request.get('note'),
                    fundraisingRound="1")
    pledge.save()

    # Add thank you email to a task queue
    deferred.defer(send_thank_you, email, pledge.key().id(), _queue="mail")

    self.response.write('Ok.')


app = webapp2.WSGIApplication([
  ('/total', GetTotalHandler),
  ('/pledge.do', PledgeHandler),
  ('/', MainHandler)
], debug=True)
