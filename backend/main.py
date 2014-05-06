import jinja2
import json
import logging
import webapp2

from google.appengine.api import mail, memcache
from google.appengine.ext import deferred

import stripe
import model

import config_NOCOMMIT

stripe.api_key = config_NOCOMMIT.STRIPE_SECRET_KEY

# This gets added to every pledge calculation
BASE_TOTAL = 42209600

class Error(Exception): pass

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates/'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def send_thank_you(name, email, url_nonce, amount_cents):
  """ Deferred email task """

  sender = 'MayOne no-reply <noreply@mayday-pac.appspotmail.com>'
  subject = 'Thank you for your pledge'
  message = mail.EmailMessage(sender=sender, subject=subject)
  message.to = email

  format_kwargs = {
    # TODO: Use the person's actual name
    'name': name,
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
    if data is None:
      logging.info('Total cache miss')
      total = BASE_TOTAL
      for pledge in model.Pledge.all():
        if pledge.imported_wp_post_id is None:
          total += pledge.amountCents
      data = str(total)
      memcache.add(GetTotalHandler.TOTAL_KEY, data, 300)
    self.response.headers['Content-Type'] = 'application/javascript'
    self.response.write('%s(%s)' % (self.request.get('callback'), data))


class GetStripePublicKeyHandler(webapp2.RequestHandler):
  def get(self):
    if not model.Config.get().stripe_public_key:
      raise Error('No public key in DB')
    self.response.write(model.Config.get().stripe_public_key)


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
    name = data.get('name', '')

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

    customer = stripe.Customer.create(card=token, email=email)

    pledge = model.addPledge(
            email=email, stripe_customer_id=customer.id, amount_cents=amount,
            occupation=occupation, employer=employer, phone=phone,
            target=target, note=self.request.get("note"))

    # Add thank you email to a task queue
    deferred.defer(send_thank_you, name or email, email,
                   pledge.url_nonce, amount, _queue="mail")
    self.response.write('Ok.')


class UserUpdateHandler(webapp2.RequestHandler):
    def get(self, url_nonce):
        user = model.User.all().filter("url_nonce =", url_nonce).get()
        if user is None:
            self.error(404)
            self.response.write('This page was not found')
            return

        template = JINJA_ENVIRONMENT.get_template('user-update.html')
        self.response.write(template.render({'user': user}))

    def post(self, url_nonce):
        try:
            user = model.User.all().filter("url_nonce =", url_nonce).get()
            if user is None:
                self.error(404)
                self.response.write('This page was not found')
                return

            user.occupation = self.request.get('occupation')
            user.employer = self.request.get('employer')
            user.phone = self.request.get('phone')
            user.target = self.request.get('target')
            user.put()
            template = JINJA_ENVIRONMENT.get_template('user-update.html')
            ctx = {'user': user, 'success': True}
            self.response.write(template.render(ctx))
        except:
            self.error(400)
            self.response.write('There was a problem submitting the form')
            return


app = webapp2.WSGIApplication([
  ('/total', GetTotalHandler),
  ('/stripe_public_key', GetStripePublicKeyHandler),
  ('/pledge.do', PledgeHandler),
  ('/user-update/(\w+)', UserUpdateHandler),
  ('/campaigns/may-one', EmbedHandler),
  ('/campaigns/may-one/', EmbedHandler)
], debug=False)
