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
import urllib2
from google.appengine.ext import db

import stripe

stripe.api_key = "sk_test_W9JDlj3jnfWkaEg8OHpVjVcX"



class Pledge(db.Model):
  donationTime = db.DateTimeProperty(auto_now_add=True)
  email = db.EmailProperty(required=True)
  amountCents = db.IntegerProperty(required=True)
  stripeCustomer = db.StringProperty(required=True)
  note = db.TextProperty(required=False)

  fundraisingRound = db.StringProperty(required=True)


class MainHandler(webapp2.RequestHandler):
  def get(self):
    self.response.write('Hello world!')


class PledgeHandler(webapp2.RequestHandler):
  def get(self):
    token = self.request.get('token')
    email = self.request.get('email')

    try:
      amount = int(self.request.get('amount'))
    except ValueError:
      self.error(400)
      self.response.write('Invalid request')
      return

    if not (token and email and amount):
      self.error(400)
      self.response.write('Invalid request')
      return

    customer = stripe.Customer.create(card=token)

    pledge = Pledge(email=email,
                    amountCents=amount,
                    stripeCustomer=customer.id,
                    note=self.request.get('note'),
                    fundraisingRound="1")
    pledge.save()
    self.response.write('Ok.')



app = webapp2.WSGIApplication([
  ('/pledge.do', PledgeHandler),
  ('/', MainHandler)
], debug=True)
