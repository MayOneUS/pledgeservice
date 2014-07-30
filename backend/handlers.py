"""Handlers for MayOne.US."""

from collections import namedtuple, defaultdict
import datetime
import json
import logging
import cgi
import base64
import urllib

from google.appengine.api import mail
from google.appengine.ext import db
from google.appengine.ext import deferred
from google.appengine.api import urlfetch
from google.appengine.api import memcache

import validictory
import webapp2


import cache
import model
import templates
import util

import pprint
import urlparse
import paypal


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


class PaymentError(Exception):
  pass


class StripeBackend(object):
  """Interface which contacts stripe."""

  def CreateCustomer(self, email, card_token):
    """Creates a stripe customer so we can charge them later.

    Returns: A string customer id.
    """
    raise NotImplementedError()

  def RetrieveCardData(self, customer_id):
    """Retrieves a stripe customer's card data, given the id.

    Returns: A card dictionary
    """
    raise NotImplementedError()

  def Charge(self, customer_id, amount_cents):
    """Charges a customer and returns an identifier for the charge."""
    raise NotImplementedError()


class MailingListSubscriber(object):
  """Interface which signs folks up for emails."""
  def Subscribe(self, email, first_name, last_name, amount_cents, ip_addr, time,
                source, phone=None, zipcode=None, volunteer=None, skills=None,
                rootstrikers=None, nonce=None, pledgePageSlug=None):
    raise NotImplementedError()


_STR = dict(type='string')
_STR_optional = dict(type='string', required=False)

PLEDGE_SCHEMA = dict(
  type='object',
  properties=dict(
    email=_STR,
    phone=dict(type='string', blank=True),
    name=_STR,
    occupation=_STR,
    employer=_STR,
    target=_STR,
    surveyResult=_STR_optional,
    subscribe=dict(type='boolean'),
    anonymous=dict(type='boolean', required=False),
    amountCents=dict(type='integer', minimum=100),
    pledgeType=dict(enum=model.Pledge.TYPE_VALUES, required=False),
    team=dict(type='string', blank=True),

    payment=dict(type='object',
                 properties=dict(
                   STRIPE=dict(type='object',
                               required=False,
                               properties=dict(token=_STR)),
                   PAYPAL=dict(type='object',
                               required=False,
                               properties=dict(step=_STR_optional)),
                 )
               ),
  )
)


def pledge_helper(handler, data, stripe_customer_id, stripe_charge_id, paypal_payer_id, paypal_txn_id):
    env = handler.app.config['env']

    if 'last_name' in data:
      last_name = data['last_name']
      if 'first_name' in data:
        first_name = data['first_name']
      else:
        first_name = ''
    else:
      # Split apart the name into first and last. Yes, this sucks, but adding the
      # name fields makes the form look way more daunting. We may reconsider this.
      name_parts = data['name'].split(None, 1)
      first_name = name_parts[0]
      if len(name_parts) == 1:
        last_name = ''
        logging.warning('Could not determine last name: %s', data['name'])
      else:
        last_name = name_parts[1]

    if not 'surveyResult' in data:
      data['surveyResult'] = ''

    if not 'city' in data:
      data['city'] = None

    if not 'address' in data:
      data['address'] = None
    else:
      logging.info('Address was: ' + str( data['address']))

    if not 'state' in data:
      data['state'] = None

    if not 'zipCode' in data:
      data['zipCode'] = None

    if not 'bitpay_invoice_id' in data:
      data['bitpay_invoice_id'] = None

    amountCents = data['amountCents']

    user, pledge = model.addPledge(email=data['email'],
                             stripe_customer_id=stripe_customer_id,
                             stripe_charge_id=stripe_charge_id,
                             paypal_payer_id=paypal_payer_id,
                             paypal_txn_id=paypal_txn_id,
                             amount_cents=amountCents,
                             first_name=first_name,
                             last_name=last_name,
                             occupation=data['occupation'],
                             employer=data['employer'],
                             phone=data['phone'],
                             target=data['target'],
                             surveyResult=data['surveyResult'],
                             pledge_type=data.get(
                               'pledgeType', model.Pledge.TYPE_CONDITIONAL),
                             team=data['team'],
                             mail_list_optin=data['subscribe'],
                             anonymous=data.get('anonymous', False),
                             address=str(data['address']),
                             city=data['city'],
                             state=data['state'],
                             zipCode=data['zipCode'],
                             bitpay_invoice_id = data['bitpay_invoice_id']
                             )

    if data['subscribe']:
      env.mailing_list_subscriber.Subscribe(
        email=data['email'],
        first_name=first_name, last_name=last_name,
        amount_cents=amountCents,
        ip_addr=handler.request.remote_addr,
        time=datetime.datetime.now(),
        source='pledge',
        phone=data['phone'],
        nonce=user.url_nonce)

    # Add to the total.
    model.ShardedCounter.increment('TOTAL-5', amountCents)

    if data['team']:
      cache.IncrementTeamPledgeCount(data['team'], 1)
      cache.IncrementTeamTotal(data['team'], amountCents)

    totalStr = '$%d' % int(amountCents / 100)
    format_kwargs = {
      'name': data['name'].encode('utf-8'),
      'url_nonce': pledge.url_nonce,
      'total': totalStr,
      'user_url_nonce': user.url_nonce
    }

    text_body = open('email/thank-you.txt').read().format(**format_kwargs)
    html_body = open('email/thank-you.html').read().format(**format_kwargs)

    env.mail_sender.Send(to=data['email'].encode('utf-8'),
                         subject='Thank you for your pledge',
                         text_body=text_body,
                         html_body=html_body)

    if amountCents > 100000:
      format_kwargs = {
        'name': data['name'].encode('utf-8'),
        'total': totalStr,
        'phone': data['phone'],
        'email': data['email'],
      }

      lessig_body = open('email/lessig-notify.txt').read().format(**format_kwargs)
      logging.info('Sending ' + lessig_body)
      env.mail_sender.Send(to='lessig@mac.com',
                           subject='A donation for %s has come in from %s %s' % (totalStr, first_name, last_name),
                           text_body=lessig_body,
                           html_body='<html><body>' + lessig_body + '</html></body>')

    id = str(pledge.key())
    receipt_url = '/receipt/%s?auth_token=%s' % (id, pledge.url_nonce)

    return id, pledge.url_nonce, receipt_url


class PledgeHandler(webapp2.RequestHandler):
  """RESTful handler for pledge objects."""

  def post(self):
    """Create a new pledge, and update user info."""
    util.EnableCors(self)
    self.response.headers['Content-Type'] = 'application/json'
    env = self.app.config['env']

    try:
      data = json.loads(self.request.body)
    except ValueError, e:
      logging.warning('Bad JSON request: %s', e)
      self.error(400)
      self.response.write('Invalid request')
      return

    try:
      validictory.validate(data, PLEDGE_SCHEMA)
    except ValueError, e:
      logging.warning('Schema check failed: %s', e)
      self.error(400)
      self.response.write('Invalid request')
      return

    # Do any server-side processing the payment processor needs.
    stripe_customer_id = None
    stripe_charge_id = None
    if 'STRIPE' in data['payment']:
      try:
        logging.info('Trying to create stripe customer %s' % data['email'])
        stripe_customer = env.stripe_backend.CreateCustomer(
          email=data['email'], card_token=data['payment']['STRIPE']['token'])
        stripe_customer_id = stripe_customer.id
        logging.info('Trying to extract address for %s' % data['email'])
        if len(stripe_customer.cards.data) > 0:
          card_data = stripe_customer.cards.data[0]
          if 'address_line1' in card_data:
            data['address'] = card_data['address_line1']
            if card_data['address_line2']:
              data['address'] += ', %s' % card_data['address_line2']
          if 'address_city' in card_data:
            data['city'] = card_data['address_city']
          if 'address_state' in card_data:
            data['state'] = card_data['address_state']
          if 'address_zip' in card_data:
            data['zipCode'] = card_data['address_zip']
        logging.info('Trying to charge %s' % data['email'])
        stripe_charge_id = env.stripe_backend.Charge(stripe_customer_id,
                                                     data['amountCents'])

        logging.info('Got charge id %s' % stripe_charge_id)
      except PaymentError, e:
        logging.warning('Payment error: %s', e)
        self.error(400)
        json.dump(dict(paymentError=str(e)), self.response)
        return

    else:
      logging.warning('No payment processor specified: %s', data)
      self.error(400)
      return

    id, auth_token, receipt_url = pledge_helper(self, data, stripe_customer_id, stripe_charge_id, None, None)

    json.dump(dict(id=id,
                   auth_token=auth_token,
                   receipt_url=receipt_url), self.response)


  def options(self):
    util.EnableCors(self)

class SubscribeHandler(webapp2.RequestHandler):
  """RESTful handler for subscription requests."""
  # https://www.pivotaltracker.com/s/projects/1075614/stories/71725060

  def post(self):
    env = self.app.config['env']

    logging.info('body: %s' % self.request.body)

    email_input = cgi.escape(self.request.get('email'))
    if len(email_input) == 0:
      logging.warning("Bad Request: required field (email) missing.")
      self.error(400)
      return

    first_name = cgi.escape(self.request.get('first_name'))
    if len(first_name) == 0:
      first_name = None

    last_name = cgi.escape(self.request.get('last_name'))
    if len(last_name) == 0:
      last_name = None

    phone_input = cgi.escape(self.request.get('phone'))
    if len(phone_input) == 0:
      phone_input = None

    zipcode_input = cgi.escape(self.request.get('zipcode'))
    if len(zipcode_input) == 0:
      zipcode_input = None

    phone_input = cgi.escape(self.request.get('phone'))
    if len(phone_input) == 0:
      phone_input = None

    volunteer_input = cgi.escape(self.request.get('volunteer')) # "YES" or "NO"
    if volunteer_input == 'on':
      volunteer_input = 'Yes'
    elif volunteer_input == 'off':
      volunteer_input = ''

    skills_input = cgi.escape(self.request.get('skills')) #Free text, limited to 255 char
    if len(skills_input) == 0:
      skills_input = None

    rootstrikers_input = cgi.escape(self.request.get('rootstrikers')) #Free text, limited to 255 char
    if rootstrikers_input=='on':
      rootstrikers_input = 'Yes'
    elif rootstrikers_input=='off':
      rootstrikers_input = ''

    source_input = cgi.escape(self.request.get('source'))
    if len(source_input) == 0:
      source_input = 'subscribe'

    pledgePageSlug_input = cgi.escape(self.request.get('pledgePageSlug'))
    if len(pledgePageSlug_input) == 0:
      pledgePageSlug_input = ''
      
    otherVars = {}
    # get any parameter that looks like MERGE something
    for argName in self.request.arguments():
      if argName.startswith('MERGE'):
        arg = self.request.get(argName)
        otherVars[argName] = arg    
    
    env.mailing_list_subscriber.Subscribe(
      email=email_input,
      first_name=first_name, last_name=last_name,
      amount_cents=None,
      ip_addr=self.request.remote_addr,
      time=datetime.datetime.now(),
      source=source_input,
      phone=phone_input,
      zipcode=zipcode_input,
      volunteer=volunteer_input,
      skills=skills_input,
      rootstrikers=rootstrikers_input,
      pledgePageSlug=pledgePageSlug_input,
      otherVars=otherVars
      )

    util.EnableCors(self)
    redirect_input = cgi.escape(self.request.get('redirect'))
    if len(redirect_input)>0:
      redirect_url = '%s?email=%s&source=%s' % (redirect_input, email_input, source_input)
    else:
      redirect_url = '/pledge?email=%s' % email_input
    self.redirect(str(redirect_url))

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

    user = model.User.get_by_key_name(pledge.email)
    if user is None:
      logging.warning('pledge had missing user: %r, %r', id, pledge.email)
      self.error(404)
      self.response.write('Not found')

    # allow this one pledge so test receipt can be viewed
    if (id != 'agxzfm1heWRheS1wYWNyEwsSBlBsZWRnZRiAgICAlZG2CAw'):
      auth_token = self.request.get('auth_token')
      if not util.ConstantTimeIsEqual(auth_token, pledge.url_nonce):
        self.error(403)
        self.response.write('Access denied')
        return

    template = templates.GetTemplate('receipt.html')
    self.response.write(template.render(dict(pledge=pledge, user=user)))


class PaymentConfigHandler(webapp2.RequestHandler):
  def get(self):
    util.EnableCors(self)
    env = self.app.config['env']
    if not env.stripe_public_key:
      raise Error('No stripe public key in DB')
    params = dict(testMode=(env.app_name == u'local'),
                  stripePublicKey=env.stripe_public_key)

    self.response.headers['Content-Type'] = 'application/json'
    json.dump(params, self.response)

  options = util.EnableCors

class NumPledgesHandler(webapp2.RequestHandler):
  def get(self):
    util.EnableCors(self)

    WP_PLEDGES = 4099
    VERSION_11_AND_UNDER = 11743

    count = memcache.get('TOTAL-PLEDGES')
    if not count:
      query = model.Pledge.all(keys_only=True).filter('model_version >', 11)
      i = 0
      while True:
          result = query.fetch(1000)
          i = i + len(result)
          if len(result) < 1000:
              break
          cursor = query.cursor()
          query.with_cursor(cursor)
      count = i + WP_PLEDGES + VERSION_11_AND_UNDER
      memcache.set('TOTAL-PLEDGES', count, 120)

    self.response.headers['Content-Type'] = 'application/json'
    json.dump({'count':count}, self.response)

  options = util.EnableCors

class TotalHandler(webapp2.RequestHandler):
  # These get added to every pledge total calculation
  PRE_SHARDING_TOTAL = 59767534  # See model.ShardedCounter
  WP_PLEDGE_TOTAL = 41326868
  DEMOCRACY_DOT_COM_BALANCE = 10156073
  CHECKS_BALANCE = 9708000  # lol US government humor

  def get(self):
    util.EnableCors(self)
    total = (TotalHandler.PRE_SHARDING_TOTAL +
             TotalHandler.WP_PLEDGE_TOTAL +
             TotalHandler.DEMOCRACY_DOT_COM_BALANCE +
             TotalHandler.CHECKS_BALANCE)
    total += model.ShardedCounter.get_count('TOTAL-5')

    result = dict(totalCents=total)

    team = self.request.get("team")
    if team:
      team_pledges = cache.GetTeamPledgeCount(team) or 0
      team_total = cache.GetTeamTotal(team) or 0
      try:
        # there are some memcache values with string values
        team_total = int(team_total)
      except ValueError, e:
        logging.exception("non-integral team total: %r", team_total)
        team_total = 0

      if not (team_pledges and team_total):
        for pledge in model.Pledge.all().filter("team =", team):
          team_pledges += 1
          team_total += pledge.amountCents
        # There was a pledge made to this team that was not made through Stripe
        if team == 'ahJzfm1heWRheS1wYWMtdGVhbXNyEQsSBFRlYW0YgICAgP7esAgM':
          team_pledges +=1
          team_total += 1000000
        cache.SetTeamPledgeCount(team, team_pledges)
        cache.SetTeamTotal(team, team_total)

      result['team'] = team
      result['teamPledges'] = team_pledges
      result['teamTotalCents'] = team_total

    self.response.headers['Content-Type'] = 'application/json'
    json.dump(result, self.response)

  options = util.EnableCors


class ThankTeamHandler(webapp2.RequestHandler):
  def post(self):
    env = self.app.config['env']
    util.EnableCors(self)

    for field in ['team', 'reply_to', 'subject', 'message_body', 'new_members']:
      if not field in self.request.POST:
        msg = "Bad Request: required field %s missing." % field
        logging.warning(msg)
        self.error(400)
        self.response.write(msg)
        return self.response

    # get the pldedges for this team, excluding the reply_to
    pledges = model.Pledge.all().filter(
      'team =',self.request.POST['team'])
    # .filter(
      # 'email !=', self.request.POST['reply_to'])

    # yes this is executing another query, and it's ok because
    # this will be done so infrequently
    # FIXME: lookup from cache.Get.. or TeamTotal once those are sorted out
    total_pledges = model.Pledge.all().filter(
      'team =',self.request.POST['team']).count()

    # if only sending to new members, filter out those that have already received emails
    if self.request.POST['new_members'] == 'True':
      pledges = pledges.filter('thank_you_sent_at =', None)

    i = 0
    for pledge in pledges:
      env.mail_sender.Send(to=pledge.email,
                     subject=self.request.POST['subject'],
                     text_body=self.request.POST['message_body'],
                     html_body=self.request.POST['message_body'],
                     reply_to=self.request.POST['reply_to'])
      i += 1
      # set the thank_you_sent_at for users after sending
      # FIXME: make sure the send was successful
      pledge.thank_you_sent_at = datetime.datetime.now()
      pledge.put()

    logging.info('THANKING: %d PLEDGERS!!' % i)
    response_data = {'num_emailed': i, 'total_pledges': total_pledges}
    self.response.content_type = 'application/json'
    self.response.write(json.dumps(response_data))

  options = util.EnableCors


class PledgersHandler(webapp2.RequestHandler):

  def get(self):
    util.EnableCors(self)

    team = self.request.get("team")
    if not team:
      self.error(400)
      self.response.write('team required')
      return

    pledgers = defaultdict(lambda: 0)

    for pledge in model.Pledge.all().filter("team =", team):
      if pledge.anonymous:
        pledgers["Anonymous"] += pledge.amountCents
        continue
      user = model.User.get_by_key_name(pledge.email)
      if user is None or (not user.first_name and not user.last_name):
        pledgers["Anonymous"] += pledge.amountCents
        continue
      name = ("%s %s" % (user.first_name or "", user.last_name or "")).strip()
      pledgers[name] += pledge.amountCents

    pledgers_by_amount = []
    for name, amount in pledgers.iteritems():
      pledgers_by_amount.append((amount, name))
    pledgers_by_amount.sort(reverse=True)

    result = {"pledgers": [name for _, name in pledgers_by_amount]}

    self.response.headers['Content-Type'] = 'application/json'
    json.dump(result, self.response)

  options = util.EnableCors


class LeaderboardHandler(webapp2.RequestHandler):

  def get(self):
    util.EnableCors(self)

    offset = int(self.request.get("offset") or 0)
    limit = int(self.request.get("limit") or 25)
    orderBy = self.request.get("orderBy") or "-totalCents"

    teams = []

    for tt in model.TeamTotal.all().order(orderBy).run(
        offset=offset, limit=limit):
      teams.append({
          "team": tt.team,
          "total_cents": tt.totalCents,
          "num_pledges": tt.num_pledges})

    self.response.headers['Content-Type'] = 'application/json'
    json.dump({"teams": teams}, self.response)

  options = util.EnableCors


class BitcoinStartHandler(webapp2.RequestHandler):
  """RESTful handler for Paypal pledge objects."""

  def post(self):
    """Create a new TempPledge, and update user info."""
    util.EnableCors(self)

    try:
      data = json.loads(self.request.body)
    except ValueError, e:
      logging.warning('Bad JSON request: %s', str(e))
      self.error(400)
      self.response.write('Invalid request')
      return

    try:
      validictory.validate(data, PLEDGE_SCHEMA)
    except ValueError, e:
      logging.warning('Schema check failed: %s', str(e))
      self.error(400)
      self.response.write('Invalid request')
      return

    temp_pledge = model.TempPledge(
      model_version=model.MODEL_VERSION,
      email=data["email"],
      name=data["name"],
      phone=data["phone"],
      occupation=data["occupation"],
      employer=data["employer"],
      target=data["target"],
      subscribe=data["subscribe"],
      amountCents=data["amountCents"],
      firstName=data["firstName"],
      lastName=data["lastName"],
      address=data["address"],
      city=data["city"],
      state=data["state"],
      zipCode=data["zip"],
      bitcoinConfirm=data["bitcoinConfirm"],
      team=data["team"]
    )
    temp_key = temp_pledge.put()
    temp_key_str = str(temp_key)

    try:
      resp_dict = self._send_to_bitpay(data["amountCents"], temp_key_str)
      json.dump({"bitpay_url": resp_dict["url"]}, self.response)
      temp_pledge.bitpay_invoice_id = resp_dict["id"]
      logging.info('Created invoice with id ' + resp_dict["id"])
      temp_pledge.put()
      return
    except Exception, e:
      logging.warning('BitcoinStart failed: ' + str(e))
      self.error(400)

  def _send_to_bitpay(self, amountCents, temp_key_str):
    price_in_dollars = int(amountCents) / 100.0
    apiKey = model.Secrets.get().bitpay_api_key
    uname = base64.b64encode(apiKey)
    headers = {'Authorization': 'Basic ' + uname }

    callbackUrl = self.request.host_url + "/r/bitcoin_notifications"
    logging.info('CALLBACK URL WILL BE: ' + callbackUrl)

    post_data = {
      'posData': temp_key_str,
      'price': price_in_dollars,
      'notificationURL': self.request.host_url + "/r/bitcoin_notifications",
      'currency': 'USD',
      # 'buyerName': data["name"],
      # 'buyerEmail': data["email"]
    }

    payload = urllib.urlencode(post_data)
    logging.info('calling URL fetchee')

    result = urlfetch.fetch(
      url='https://bitpay.com/api/invoice/',
      payload=payload,
      method=urlfetch.POST,
      headers=headers,
      validate_certificate=True
    )

    if result.status_code == 200:
      response_dict = json.loads(result.content)
      return response_dict
    else:
      logging.warning('BitcoinStart failed: ' + str(result.content))
      self.error(400)
      self.response.write('Invalid request')
      return

  options = util.EnableCors


class BitcoinNotificationsHandler(webapp2.RequestHandler):
  def post(self):
    # TODO: check SSL cert
    # add bitpay invoice ID to pledge record

    try:
      data = json.loads(self.request.body)
    except ValueError, e:
      logging.warning('Bad JSON request: %s', str(e))
      logging.info('Bad request was: ' + str(self.request.body))
      self.error(400)
      self.response.write('Invalid request')
      return

    invoiceID = data["id"]
    posData = data["posData"]
    logging.info('Bitpay notifications for. Invoice ID: %s, Status: %s' % (invoiceID, data.get('status')))

    key = db.Key(posData)
    temp_pledge = model.TempPledge.get_by_id(key.id())


    if not temp_pledge:
      logging.warning('could not find temp pledge from posData')
      self.error(400)
      return

    # check to make sure this isn't a duplicate notification
    # as they try up to 5 times
    if temp_pledge.pledge_id:
      return self.response

    if not data.get('status') == 'confirmed':
      logging.info('Non comfirmed transaction. Ignoring. Invoice ID: %s, Status: %s' % (invoiceID, data.get('status')))
      self.response.write('Thanks. We got this, but ignored it.')
      return

    paid_price = float(data["price"])
    if paid_price > 100:
      logging.warning('bitpay paid amount > $100')

    temp_pledge_data = {
      'bitpay_invoice_id': temp_pledge.bitpay_invoice_id,
      'name': temp_pledge.firstName,
      'email': temp_pledge.email,
      'phone': temp_pledge.phone,
      'occupation': temp_pledge.occupation,
      'employer': temp_pledge.employer,
      'target': temp_pledge.target,
      'subscribe': temp_pledge.subscribe,
      'team': temp_pledge.team,
      'first_name': temp_pledge.firstName,
      'last_name': temp_pledge.lastName,
      'address': temp_pledge.address,
      'city': temp_pledge.city,
      'state': temp_pledge.state,
      'zipCode': temp_pledge.zipCode,
      'amountCents': int(paid_price * 100),
      'pledgeType': 'DONATION'
    }

    #if the price paid in the confirmed invoice is different, update it here
    temp_pledge_data["price"] = data["price"]
    if temp_pledge.amountCents != data["price"]:
      logging.warning('bitpay confirmed amount is different')


    id, auth_token, receipt_url = pledge_helper(self, temp_pledge_data, None,
      None, None, None)

    temp_pledge.pledge_id = id
    temp_pledge.put()

    # they just look for any 200 response
    return self.response

  options = util.EnableCors


# Paypal Step 1: We initiate a PAYPAL transaction
class PaypalStartHandler(webapp2.RequestHandler):
  """RESTful handler for Paypal pledge objects."""

  def post(self):
    """Create a new pledge, and update user info."""
    util.EnableCors(self)
    self.response.headers['Content-Type'] = 'application/json'
    env = self.app.config['env']

    try:
      data = json.loads(self.request.body)
    except ValueError, e:
      logging.warning('Bad JSON request: %s', str(e))
      self.error(400)
      self.response.write('Invalid request')
      return

    try:
      validictory.validate(data, PLEDGE_SCHEMA)
    except ValueError, e:
      logging.warning('Schema check failed: %s', str(e))
      self.error(400)
      self.response.write('Invalid request')
      return



    rc, paypal_url = paypal.SetExpressCheckout(self.request.host_url, data)
    if rc:
        json.dump(dict(paypal_url=paypal_url), self.response)
        return

    logging.warning('PaypalStart failed')
    self.error(400)

  options = util.EnableCors


# Paypal Step 2: Paypal returns to us, telling us the user has agreed.  Book it.
class PaypalReturnHandler(webapp2.RequestHandler):
  def get(self):
    token = self.request.get("token")
    if not token:
      token = self.request.get("TOKEN")

    payer_id = self.request.get("PayerID")
    if not payer_id:
      payer_id = self.request.get("PAYERID")

    if not token or not payer_id:
      logging.warning("Paypal completion missing data: " + self.request.url)
      self.error(400);
      self.response.write("Unusual error: no token or payer id from Paypal.  Please contact info@mayday.us and report these details:")
      self.response.write(self.request.url)
      return


    # Fetch the details of this pending transaction
    form_fields = {
      "METHOD": "GetExpressCheckoutDetails",
      "TOKEN": token
    }
    rc, results = paypal.send_request(form_fields)
    if not rc:
      self.error(400);
      self.response.write("Unusual error: Could not get payment details from Paypal.  Please contact info@mayday.us and report these details:")
      self.response.write(pprint.pformat(results))
      return

    data = dict()

    name = ""
    if 'FIRSTNAME' in results:
        data['first_name'] = results['FIRSTNAME'][0]
        name += results['FIRSTNAME'][0]
    if 'MIDDLENAME' in results:
        name += " " + results['FIRSTNAME'][0]
    if 'LASTNAME' in results:
        data['last_name'] = results['LASTNAME'][0]
        if len(name) > 0:
            name += " "
        name += results['LASTNAME'][0]
    data['name'] = name

    paypal_email = results['EMAIL'][0]
    amount = results['PAYMENTREQUEST_0_AMT'][0]
    cents = int(float(amount)) * 100
    data['amountCents'] = cents
    payer_id = results['PAYERID'][0]
    custom = urlparse.parse_qs(results['CUSTOM'][0])
    if custom['email'][0] != paypal_email:
        logging.warning("User entered email [%s], but purchased with email [%s]" % (custom['email'][0], paypal_email))

    for v in { 'email', 'phone', 'occupation', 'employer', 'target', 'subscribe', 'anonymous', 'pledgeType', 'team', 'surveyResult' }:
      if v in custom:
        data[v] = custom[v][0]
      else:
        data[v] = None

    if 'team' not in custom:
        data['team'] = self.request.cookies.get("last_team_key")

    data['subscribe'] =  data['subscribe'] == 'True'

    rc, results = paypal.DoExpressCheckoutPayment(token, payer_id, amount, custom)
    if rc:
      request_data = {
         'METHOD': 'GetTransactionDetails',
         'TRANSACTIONID': results['PAYMENTINFO_0_TRANSACTIONID'][0]
      }
      rc, txn_data = paypal.send_request(request_data)
      if rc:
        if 'SHIPTOSTREET' in txn_data:
          data['address'] = txn_data['SHIPTOSTREET'][0]
          if 'SHIPTOSTREET2' in txn_data:
            data['address'] += ', %s' % txn_data['SHIPTOSTREET2'][0]
        if 'SHIPTOCITY' in txn_data:
          data['city'] = txn_data['SHIPTOCITY'][0]
        if 'SHIPTOSTATE' in txn_data:
          data['state'] = txn_data['SHIPTOSTATE'][0]
        if 'SHIPTOZIP' in txn_data:
          data['zipCode'] = txn_data['SHIPTOZIP'][0]

      id, auth_token, receipt_url = pledge_helper(self, data, None, None, payer_id, results['PAYMENTINFO_0_TRANSACTIONID'][0])
      self.redirect(receipt_url)

    else:
      self.error(400);
      self.response.write("Unusual error: Could not get complete payment from Paypal.  Please contact info@mayday.us and report these details:")
      self.response.write(pprint.pformat(results))
      return


HANDLERS = [
  ('/r/leaderboard', LeaderboardHandler),
  ('/r/pledgers', PledgersHandler),
  ('/r/pledge', PledgeHandler),
  ('/receipt/(.+)', ReceiptHandler),
  ('/r/payment_config', PaymentConfigHandler),
  ('/r/total', TotalHandler),
  ('/r/num_pledges', NumPledgesHandler),
  ('/r/thank', ThankTeamHandler),
  ('/r/subscribe', SubscribeHandler),
  ('/r/bitcoin_start', BitcoinStartHandler),
  ('/r/bitcoin_notifications', BitcoinNotificationsHandler),
  ('/r/paypal_start', PaypalStartHandler),
  ('/r/paypal_return', PaypalReturnHandler),
]
