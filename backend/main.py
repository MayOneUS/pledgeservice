import datetime
import itertools
import jinja2
import json
import logging
import urlparse
import webapp2

from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import deferred

from mailchimp import mailchimp

import model
import stripe
import wp_import

# These get added to every pledge calculation
PRE_SHARDING_TOTAL = 27425754  # See model.ShardedCounter
WP_PLEDGE_TOTAL = 41326868
DEMOCRACY_DOT_COM_BALANCE = 9036173
CHECKS_BALANCE = 7655200  # lol US government humor


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


def subscribe_to_mailchimp(email_to_subscribe, first_name, last_name,
                           amount, opt_in_IP, source):
  mailchimp_api_key = model.Config.get().mailchimp_api_key
  mailchimp_list_id = model.Config.get().mailchimp_list_id
  mc = mailchimp.Mailchimp(mailchimp_api_key)

  merge_vars = {
    'FNAME': first_name,
    'LNAME': last_name,
    'optin_ip': opt_in_IP,
    'optin_time': str(datetime.datetime.now())
  }

  if source:
    merge_vars['SOURCE'] = source

  if amount:
    amountDollars = '{0:.02f}'.format(float(amount) / 100.0)
    merge_vars['LASTPLEDGE'] = amountDollars

  # list ID and email struct
  mc.lists.subscribe(id=mailchimp_list_id,
                     email={'email': email_to_subscribe },
                     merge_vars=merge_vars,
                     double_optin=False,
                     update_existing=True,
                     send_welcome=False)


# Respond to /OPTION requests in a way that allows cross site requests
# TODO(hjfreyer): Pull into some kind of middleware?
def enable_cors(handler):
  if 'Origin' in handler.request.headers:
    origin = handler.request.headers['Origin']
    _, netloc, _, _, _, _ = urlparse.urlparse(origin)    
    if not (netloc == 'mayone.us' or netloc.endswith('.mayone.us')):
      logging.warning('Invalid origin: ' + origin)
      handler.error(403)
      return

    handler.response.headers.add_header("Access-Control-Allow-Origin", origin)
    handler.response.headers.add_header("Access-Control-Allow-Methods", "POST")
    handler.response.headers.add_header("Access-Control-Allow-Headers",
                                        "content-type, origin")

# TODO(hjfreyer): Tests!!
class ContactHandler(webapp2.RequestHandler):
  def post(self):
    data = json.loads(self.request.body)
    ascii_name = data["name"].encode('ascii', errors='ignore')
    ascii_email = data["email"].encode('ascii', errors='ignore')
    ascii_subject = data["subject"].encode('ascii', errors='ignore')
    ascii_body = data["body"].encode('ascii', errors='ignore')

    replyto = '%s <%s>' % (ascii_name, ascii_email)
    message = mail.EmailMessage(sender=('MayOne no-reply <noreply@%s.appspotmail.com>' %
                                           model.Config.get().app_name),
                                reply_to=replyto,
                                subject=ascii_subject)
    message.to = "info@mayone.us"
    message.body = 'FROM: %s\n\n%s' % (ascii_email, ascii_body)
    message.send()
    enable_cors(self)
    self.response.write('Ok.')

  def options(self):
    enable_cors(self)


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
      logging.warning('Bad JSON request')
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
    name = data['name']

    occupation = data['userinfo']['occupation']
    employer = data['userinfo']['employer']
    phone = data['userinfo']['phone']
    target = data['userinfo']['target']

    # TODO(hjfreyer): Require this field.
    subscribe = data['userinfo'].get('subscribe')

    try:
      amount = int(amount)
    except ValueError:
      self.error(400)
      self.response.write('Invalid request')
      return

    if not (email and token and amount and occupation and employer and target
            and name):
      self.error(400)
      self.response.write('Invalid request: missing field')
      return

    if not mail.is_email_valid(email):
      self.error(400)
      self.response.write('Invalid request: Bad email address')
      return

    # Split apart the name into first and last. Yes, this sucks, but adding the
    # name fields makes the form look way more daunting. We may reconsider this.
    name_parts = name.split(None, 1)
    first_name = name_parts[0]
    if len(name_parts) == 1:
      last_name = ''
      logging.warning('Could not determine last name: %s', name)
    else:
      last_name = name_parts[1]

    stripe.api_key = model.Config.get().stripe_private_key
    customer = stripe.Customer.create(card=token, email=email)

    pledge = model.addPledge(
      email=email, stripe_customer_id=customer.id, amount_cents=amount,
      first_name=first_name, last_name=last_name,
      occupation=occupation, employer=employer, phone=phone,
      target=target, note=self.request.get('note'), 
      mail_list_optin=subscribe)

    # Add thank you email to a task queue
    deferred.defer(send_thank_you, name or email, email,
                   pledge.url_nonce, amount, _queue='mail')

    # Add to the total asynchronously.
    deferred.defer(model.increment_donation_total, amount,
                   _queue='incrementTotal')

    if subscribe:
      deferred.defer(subscribe_to_mailchimp,
                     email, first_name=first_name, last_name=last_name,
                     amount=amount, opt_in_IP=self.request.remote_addr,
                     source='pledged')

    response = dict(id=pledge.url_nonce)
    self.response.headers['Content-Type'] = 'application/json'
    json.dump(response, self.response)


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


class UserInfoHandler(webapp2.RequestHandler):
  def get(self, url_nonce):
    enable_cors(self)
    user = model.User.all().filter('url_nonce =', url_nonce).get()
    if user is None:
      self.error(404)
      self.response.write('user not found')
      return

    # maybe we should do sum instead?
    biggest_pledge = None
    biggest_amount = 0
    for pledge in itertools.chain(
        model.Pledge.all().filter('email =', user.email),
        model.WpPledge.all().filter('email =', user.email)):
      if (pledge.amountCents or 0) >= biggest_amount:
        biggest_pledge = pledge
        biggest_amount = (pledge.amountCents or 0)

    if biggest_pledge is None:
      self.error(404)
      self.response.write("user not found")
      return

    cus = stripe.Customer.retrieve(biggest_pledge.stripeCustomer)
    if len(cus.cards.data) == 0:
      self.error(404)
      self.response.write("user not found")
      return

    if user.first_name or user.last_name:
      # TODO(jt): we should backfill this information
      user_name = "%s %s" % (user.first_name or "", user.last_name or "")
    else:
      user_name = cus.cards.data[0].name

    zip_code = cus.cards.data[0].address_zip

    self.response.headers['Content-Type'] = 'application/javascript'
    self.response.write(json.dumps({
        "user": {
          "name": user_name,
          "pledge_amount_cents": biggest_amount,
          "zip_code": zip_code}}))

  def options(self):
    enable_cors(self)


app = webapp2.WSGIApplication([
  ('/total', GetTotalHandler),
  ('/stripe_public_key', GetStripePublicKeyHandler),
  ('/pledge.do', PledgeHandler),
  ('/user-update/(\w+)', UserUpdateHandler),
  ('/user-info/(\w+)', UserInfoHandler),
  ('/campaigns/may-one/?', EmbedHandler),
  ('/contact.do', ContactHandler),
  # See wp_import
  # ('/import.do', wp_import.ImportHandler),
], debug=False)
