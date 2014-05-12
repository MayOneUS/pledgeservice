import jinja2
import json
import logging
import webapp2

from google.appengine.api import mail
from google.appengine.ext import deferred

import model
import stripe
import util
import wp_import

# These get added to every pledge calculation
PRE_SHARDING_TOTAL = 27425754  # See model.ShardedCounter
WP_PLEDGE_TOTAL = 41326868
DEMOCRACY_DOT_COM_BALANCE = 4638250
CHECKS_BALANCE = 0  # lol US government humor


class Error(Exception): pass

JINJA_ENVIRONMENT = jinja2.Environment(
  loader=jinja2.FileSystemLoader('templates/'),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)


def send_thank_you(name, email, url_nonce, amount_cents):
  """Deferred email task"""
  sender = ('MayOne no-reply <noreply@%s.appspotmail.com>' %
            model.Config.get().app_name)
  subject = 'Thank you for your pledge'
  message = mail.EmailMessage(sender=sender, subject=subject)
  message.to = email

  format_kwargs = {
    # TODO: Figure out how to set the outgoing email content encoding.
    #  once we can set the email content encoding to utf8, we can change this
    #  to name.encode('utf-8') and not drop fancy characters. :(
    'name': name.encode('ascii', errors='ignore'),
    'url_nonce': url_nonce,
    'total': '$%d' % int(amount_cents/100)
  }

  message.body = open('email/thank-you.txt').read().format(**format_kwargs)
  message.html = open('email/thank-you.html').read().format(**format_kwargs)
  message.send()


class GetTotalHandler(webapp2.RequestHandler):
  def get(self):
    total = (PRE_SHARDING_TOTAL +
             WP_PLEDGE_TOTAL +
             DEMOCRACY_DOT_COM_BALANCE +
             CHECKS_BALANCE)
    total += model.ShardedCounter.get_count('TOTAL')
    total = int(total/100) * 100
    self.response.headers['Content-Type'] = 'application/javascript'
    self.response.write('%s(%d)' % (self.request.get('callback'), total))


class GetStripePublicKeyHandler(webapp2.RequestHandler):
  def get(self):
    if not model.Config.get().stripe_public_key:
      raise Error('No public key in DB')
    self.response.write(model.Config.get().stripe_public_key)


class EmbedHandler(webapp2.RequestHandler):
  def get(self):
    if self.request.get('widget') == '1':
      self.redirect('/embed.html')
    else:
      self.redirect('/')


class PledgeHandler(webapp2.RequestHandler):
  def post(self):
    try:
      data = json.loads(self.request.body)
    except:
      logging.Warning('Bad JSON request')
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

    stripe.api_key = model.Config.get().stripe_private_key
    customer = stripe.Customer.create(card=token, email=email)

    pledge = model.addPledge(
            email=email, stripe_customer_id=customer.id, amount_cents=amount,
            occupation=occupation, employer=employer, phone=phone,
            target=target, note=self.request.get('note'))

    # Add thank you email to a task queue
    deferred.defer(send_thank_you, name or email, email,
                   pledge.url_nonce, amount, _queue='mail')

    # Add to the total asynchronously.
    deferred.defer(model.increment_donation_total, amount,
                   _queue='incrementTotal')

    result = dict(url_nonce=pledge.url_nonce)
    json.dump(result, self.response)


class UserUpdateHandler(webapp2.RequestHandler):
  def get(self, url_nonce):
    user = model.User.all().filter('url_nonce =', url_nonce).get()
    if user is None:
      self.error(404)
      self.response.write('This page was not found')
      return

    template = JINJA_ENVIRONMENT.get_template('user-update.html')
    self.response.write(template.render({'user': user}))

  def post(self, url_nonce):
    try:
      user = model.User.all().filter('url_nonce =', url_nonce).get()
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


class ReceiptHandler(webapp2.RequestHandler):
  def get(self, email, url_nonce):
    pledges = (list(model.Pledge.all().filter('email =', email)) +
               list(model.WpPledge.all().filter('email =', email)))
    pledges = [p for p in pledges
               if util.ConstantTimeIsEqual(p.url_nonce, url_nonce)]
    if not pledges:
      self.error(404)
      self.response.write('This page was not found')
      return

    if len(pledges) > 1:
      raise Error('Multiple pledges with the same nonce')

    pledge = pledges[0]

    template = JINJA_ENVIRONMENT.get_template('receipt.html')
    self.response.write(template.render({'amount': pledge.amountCents / 100}))


app = webapp2.WSGIApplication([
  ('/total', GetTotalHandler),
  ('/stripe_public_key', GetStripePublicKeyHandler),
  ('/pledge.do', PledgeHandler),
  ('/user-update/(\w+)', UserUpdateHandler),
  ('/receipt/(.+)/(.+)', ReceiptHandler),
  ('/campaigns/may-one/?', EmbedHandler),
  # See wp_import
  # ('/import.do', wp_import.ImportHandler),
], debug=False)
