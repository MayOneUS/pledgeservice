import unittest
import copy
import urllib2
import logging
import datetime
import json

from google.appengine.api import mail_stub
from google.appengine.ext import db
from google.appengine.ext import testbed
import mox
import webapp2
import webtest

import handlers
import model
import env
import stripe as stripe_lib

class BaseTest(unittest.TestCase):
  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()

    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_urlfetch_stub()

    self.testbed.init_mail_stub()
    self.mail_stub = self.testbed.get_stub(testbed.MAIL_SERVICE_NAME)

    self.mockery = mox.Mox()
    self.stripe = self.mockery.CreateMock(handlers.StripeBackend)
    self.mailing_list_subscriber = self.mockery.CreateMock(
      handlers.MailingListSubscriber)
    self.mail_sender = env.MailSender(defer=False)

    self.env = handlers.Environment(
      app_name='unittest',
      stripe_public_key='pubkey1234',
      stripe_backend=self.stripe,
      mailing_list_subscriber=self.mailing_list_subscriber,
      mail_sender=self.mail_sender)

    from main import HANDLERS  # main import must come after other init
    self.wsgi_app = webapp2.WSGIApplication(HANDLERS + handlers.HANDLERS,
                                            config=dict(env=self.env))

    self.app = webtest.TestApp(self.wsgi_app)

  def tearDown(self):
    self.mockery.VerifyAll()
    self.testbed.deactivate()

class StripeTest(BaseTest):
  def setUp(self):
    super(StripeTest, self).setUp()
    stripe_lib.api_key = "sk_test_sm4iLzUFCeEE4l8uKe4KNDU7"
    self.pledge = dict(
      email='pika@pokedex.biz',
      phone='212-234-5432',
      name=u'Pik\u00E1 Chu',
      occupation=u'Pok\u00E9mon',
      employer='Nintendo',
      target='Republicans Only',
      subscribe=True,
      amountCents=4200,
      pledgeType='CONDITIONAL',
      team='rocket',
      thank_you_sent_at=None,
      payment=dict(
        STRIPE=dict(
        )
      ))
  def testStripeRecurring(self):
    token = stripe_lib.Token.create( 
      card={ 
      "number":'4242424242424242', 
      "exp_month": 12, 
      "exp_year": 25, 
      "cvc": '123'
      })
    recurring_pledge = copy.deepcopy(self.pledge)
    recurring_pledge["recurring"] = True
    recurring_pledge["payment"]["STRIPE"]["token"] = token.id
    req = urllib2.Request('http://localhost:8080/r/pledge')
    req.add_header('Content-Type', 'application/json')
    response = urllib2.urlopen(req, json.dumps(recurring_pledge))
    assert("id" in json.loads(response.read()))   

  def testStripePayment(self):
    token = stripe_lib.Token.create( 
      card={ "number":'4242424242424242', 
        "exp_month": 12, 
        "exp_year": 25, 
        "cvc": '123'
      })
    single_payment = copy.deepcopy(self.pledge)
    single_payment["payment"]["STRIPE"]["token"] = token.id
    req = urllib2.Request('http://localhost:8080/r/pledge')
    req.add_header('Content-Type', 'application/json')
    response = urllib2.urlopen(req, json.dumps(single_payment))
    assert("id" in json.loads(response.read()))

class PledgeTest(BaseTest):
  def setUp(self):
    super(PledgeTest, self).setUp()

    self.pledge = dict(
      email='pika@pokedex.biz',
      phone='212-234-5432',
      name=u'Pik\u00E1 Chu',
      occupation=u'Pok\u00E9mon',
      employer='Nintendo',
      target='Republicans Only',
      subscribe=True,
      amountCents=4200,
      pledgeType='CONDITIONAL',
      team='rocket',
      thank_you_sent_at=None,
      payment=dict(
        STRIPE=dict(
          token='tok_1234',
        )
      ))

    handlers.TotalHandler.PRE_SHARDING_TOTAL = 10
    handlers.TotalHandler.WP_PLEDGE_TOTAL = 11
    handlers.TotalHandler.DEMOCRACY_DOT_COM_BALANCE = 12
    handlers.TotalHandler.CHECKS_BALANCE = 13
    model.STRETCH_CACHE_MISS_TOTAL = 14

    self.balance_baseline = 60

  def expectStripe(self):
    self.stripe.CreateCustomer(
      email=self.pledge['email'],
      card_token=self.pledge['payment']['STRIPE']['token']
    ).AndReturn(env.FakeStripe().CreateCustomer(
      self.pledge['email'], self.pledge['payment']['STRIPE']['token'])
    )

    self.stripe.Charge('fake_1234', self.pledge['amountCents']) \
               .AndReturn('charge_2468')

  def expectStripeDeclined(self):
    self.stripe.CreateCustomer(
      email=self.pledge['email'],
      card_token=self.pledge['payment']['STRIPE']['token']
    ).AndReturn(env.FakeStripe().CreateCustomer(
      'failure@failure.biz', self.pledge['payment']['STRIPE']['token'])
    )

    self.stripe.Charge('doomed_customer', self.pledge['amountCents']) \
               .AndRaise(handlers.PaymentError('You got no money'))

  def expectSubscribe(self, phone=None, pledgePageSlug=None):
    if phone is None:
      phone = '212-234-5432'
    if pledgePageSlug is None:
      pledgePageSlug = '28e9-Team-Shant-is-Shant'
    self.mailing_list_subscriber \
        .Subscribe(email=self.pledge['email'],
                   first_name=u'Pik\u00E1',
                   last_name='Chu',
                   amount_cents=4200,
                   ip_addr=None,  # Not sure why this is None in unittests
                   time=mox.IsA(datetime.datetime),
                   phone=phone,
                   source='pledge',
                   nonce=mox.Regex('.*'),)
                   # pledgePageSlug=pledgePageSlug)

  def makeDefaultRequest(self, phone=None, pledgePageSlug=None):
    self.expectStripe()
    self.expectSubscribe(phone=phone,pledgePageSlug=pledgePageSlug)
    self.mockery.ReplayAll()

    return self.app.post_json('/r/pledge', self.pledge)

  def testTeamTotalModel(self):
    for _ in range(3):
      self.expectStripe()
      self.expectSubscribe()
    self.mockery.ReplayAll()

    self.assertEquals(model.TeamTotal.all().count(), 0)
    self.app.post_json('/r/pledge', self.pledge)
    tt = model.TeamTotal.all()[0]
    self.assertEquals(tt.totalCents, self.pledge["amountCents"])
    self.assertEquals(tt.num_pledges, 1)

    self.app.post_json('/r/pledge', self.pledge)
    self.app.post_json('/r/pledge', self.pledge)
    self.assertEquals(model.TeamTotal.all().count(), 1)
    tt = model.TeamTotal.all()[0]
    self.assertEquals(tt.totalCents, 12600)
    self.assertEquals(tt.num_pledges, 3)

  def testMailOnCreatePledge(self):
    self.makeDefaultRequest()

    messages = self.mail_stub.get_sent_messages(to=self.pledge["email"])
    self.assertEquals(1, len(messages))
    self.assertEquals(self.pledge["email"], messages[0].to)
    self.assertTrue('Mayday PAC' in messages[0].sender)
    self.assertEquals('Thank you for your pledge', messages[0].subject)

  def testBadJson(self):
    self.app.post('/r/pledge', '{foo', status=400)

  def testNotEnoughJson(self):
    self.app.post_json('/r/pledge', dict(email='foo@bar.com'), status=400)

  def testCreateAddsUser(self):
    resp = self.makeDefaultRequest()
    user = model.User.get_by_key_name(self.pledge['email'])
    self.assertEquals('1600 Pennsylvania Ave NW', user.address)
    self.assertEquals('Washington', user.city)
    self.assertEquals('DC', user.state)
    self.assertEquals('20500', user.zipCode)

  def testCreateAddsPledge(self):
    resp = self.makeDefaultRequest()
    pledge = db.get(resp.json['id'])
    self.assertEquals(4200, pledge.amountCents)
    self.assertEquals(resp.json['auth_token'], pledge.url_nonce)
    self.assertEquals('fake_1234', pledge.stripeCustomer)
    self.assertEquals('charge_2468', pledge.stripe_charge_id)
    self.assertEquals('rocket', pledge.team)

    user = model.User.get_by_key_name('pika@pokedex.biz')

    def assertEqualsSampleProperty(prop_name, actual):
      self.assertEquals(self.pledge[prop_name], actual)
    assertEqualsSampleProperty('email', user.email)
    self.assertEquals(u'Pik\u00E1', user.first_name)
    self.assertEquals('Chu', user.last_name)
    assertEqualsSampleProperty('occupation', user.occupation)
    assertEqualsSampleProperty('employer', user.employer)
    assertEqualsSampleProperty('phone', user.phone)
    assertEqualsSampleProperty('target', user.target)
    assertEqualsSampleProperty('subscribe', user.mail_list_optin)
    assert user.url_nonce
    assert not user.from_import

  def testCreateChargeFailure(self):
    self.assertEquals(0, model.Pledge.all().count())

    self.expectStripeDeclined()
    self.mockery.ReplayAll()

    resp = self.app.post_json('/r/pledge', self.pledge, status=400)
    self.assertEquals('You got no money', resp.json['paymentError'])

  def testSubscribes(self):
    self.expectStripe()
    self.expectSubscribe()

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', self.pledge)
    user = model.User.get_by_key_name('pika@pokedex.biz')
    assert user.mail_list_optin

  def testSubscribeOptOut(self):
    self.pledge['subscribe'] = False

    self.expectStripe()

    # Don't subscribe.

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', self.pledge)
    user = model.User.get_by_key_name('pika@pokedex.biz')
    assert not user.mail_list_optin

  def testNoPhone(self):
    self.pledge['phone'] = ''
    self.makeDefaultRequest(phone='', pledgePageSlug='')

  def testNoName(self):
    self.pledge['name'] = ''

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', self.pledge, status=400)

# TODO(hjfreyer): Make less brittle.
#   def testMail(self):
#     self.pledge['subscribe'] = False

#     self.expectStripe()

#     self.mail_sender.Send(to='pika@pokedex.biz', subject='Thank you for your pledge',
#                           text_body="""Dear Pik\xc3\xa1 Chu:

# Thank you for your pledge to the MaydayPAC. We are grateful for the support to make it possible for us to win back our democracy.

# But may I ask for one more favor?

# We will only win if we find 100 people for every person like you. It would be incredibly helpful if you could help us recruit them, ideally by sharing the link to the MayOne.US site. We've crafted something simple to copy and paste below. Or you can like us on our Facebook Page[1], or follow @MayOneUS[2] on Twitter.

# We'd be grateful for your feedback and ideas for how we can spread this message broadly. We're watching the social media space for #MaydayPAC, or you can email your ideas to info@mayone.us.

# This is just the beginning. But if we can succeed as we have so far, then by 2016, we will have taken the first critical step to getting our democracy back.

# This email serves as your receipt for your pledge of: $42

# Thank you again,

# Lessig
# lessig@mayone.us

# Suggested text:

# I just supported a SuperPAC to end all SuperPACs \xe2\x80\x94 the #MaydayPAC, citizen-funded through a crowd-funded campaign. You can check it out here: http://mayone.us.

# [1] https://www.facebook.com/mayonedotus
# [2] https://twitter.com/MayOneUS

# ----------------------
# Paid for by MayDay PAC
# Not authorized by any candidate or candidate\xe2\x80\x99s committee
# www.MayOne.us
# """,
#                           html_body='''<html>
#   <body>
#     <p>Dear Pik\xc3\xa1 Chu,</p>

#     <p>Thank you for your pledge to the MaydayPAC. We are grateful for the support to make it possible for us to win back our democracy.</p>

#     <p>But may I ask for one more favor?</p>

#     <p>We will only win if we find 100 people for every person like you. It would be incredibly helpful if you could help us recruit them, ideally by sharing the link to the MayOne.US site. We\'ve crafted something simple to copy and paste below. Or you can like us on <a href="https://www.facebook.com/mayonedotus">our Facebook Page</a>, or follow <a href="https://twitter.com/MayOneUS">@MayOneUS</a> on Twitter.</p>

#     <p>We\'d be grateful for your feedback and ideas for how we can spread this message broadly. We\'re watching the social media space for #MaydayPAC, or you can email your ideas to <a href="mailto:info@mayone.us">info@mayone.us</a>.</p>

#     <p>This is just the beginning. But if we can succeed as we have so far, then by 2016, we will have taken the first critical step to getting our democracy back.</p>

#     <p>This email serves as your receipt for your pledge of: $42</p>

#     <p>Thank you again,</p>

#     <p>
#        Lessig<br/>
#        lessig@mayone.us
#     </p>

#     <p>Suggested text:</p>
#     <p>I just supported a SuperPAC to end all SuperPACs &ndash; the #MaydayPAC, citizen-funded through a crowd-funded campaign. You can check it out here: http://mayone.us.</p>

#     <p>
#       ----------------------<br/>
#       Paid for by MayDay PAC<br/>
#       Not authorized by any candidate or candidate\xe2\x80\x99s committee<br/>
#       www.MayOne.us
#     </p>
#   </body>
# </html>
# ''')

#     # Don't subscribe.

#     self.mockery.ReplayAll()

#     self.app.post_json('/r/pledge', self.pledge)

  def testEmptyTeam(self):
    self.pledge['team'] = ''
    resp = self.makeDefaultRequest()
    pledge = db.get(resp.json['id'])
    self.assertEquals('', pledge.team)

  def testTotal(self):
    resp = self.app.get('/r/total')
    self.assertEquals(self.balance_baseline, resp.json['totalCents'])
    self.makeDefaultRequest()

    resp = self.app.get('/r/total')
    self.assertEquals(self.balance_baseline + 4200, resp.json['totalCents'])

  def testTeamTotal(self):
    for _ in range(2):
      self.expectStripe()
      self.expectSubscribe()
    self.mockery.ReplayAll()

    resp = self.app.get('/r/total?team=nobody')
    self.assertEquals(dict(
      totalCents=self.balance_baseline,
      team='nobody',
      teamPledges=0,
      teamTotalCents=0
    ), resp.json)

    resp = self.app.get('/r/total?team=rocket')
    self.assertEquals(dict(
      totalCents=self.balance_baseline,
      team='rocket',
      teamPledges=0,
      teamTotalCents=0
    ), resp.json)

    self.app.post_json('/r/pledge', self.pledge)

    resp = self.app.get('/r/total?team=nobody')
    self.assertEquals(dict(
      totalCents=self.balance_baseline + 4200,
      team='nobody',
      teamPledges=0,
      teamTotalCents=0
    ), resp.json)

    resp = self.app.get('/r/total?team=rocket')
    self.assertEquals(dict(
      totalCents=self.balance_baseline + 4200,
      team='rocket',
      teamPledges=1,
      teamTotalCents=4200,
    ), resp.json)

    self.app.post_json('/r/pledge', self.pledge)

    resp = self.app.get('/r/total?team=nobody')
    self.assertEquals(dict(
      totalCents=self.balance_baseline + 2 * 4200,
      team='nobody',
      teamPledges=0,
      teamTotalCents=0
    ), resp.json)

    resp = self.app.get('/r/total?team=rocket')
    self.assertEquals(dict(
      totalCents=self.balance_baseline + 2 * 4200,
      team='rocket',
      teamPledges=2,
      teamTotalCents=8400,
    ), resp.json)

  def testThankTeam(self):
    self.makeDefaultRequest()

    post_data = {'team': 'rocket',
      'reply_to': 'another@email.com', 'subject': 'the email subject',
      'message_body': 'the message body', 'new_members': False}

    # fails with a 400 error if the post request is missing any keys
    with self.assertRaises(Exception):
      resp = self.app.post('/r/thank', {})

    # pledge does get the email if are the reply_to
    post_data['reply_to'] = self.pledge["email"]
    resp = self.app.post('/r/thank', post_data)
    messages = self.mail_stub.get_sent_messages(to=self.pledge["email"])
    # 1 email sent is the created pledge
    self.assertEquals(len(messages), 2)
    # post response should be zero sent thank you emails
    resp_data = json.loads(resp.text)
    self.assertEquals(resp_data['num_emailed'], 1)
    self.assertEquals(resp_data['total_pledges'], 1)

    # this is the happy path
    post_data['reply_to'] = 'another@email.com'
    # self.assertEquals(model.Pledge.all()[0].thank_you_sent_at, None)
    resp = self.app.post('/r/thank', post_data)
    messages = self.mail_stub.get_sent_messages(to=self.pledge["email"])
    self.assertEquals(len(messages), 3)
    self.assertEquals(messages[2].reply_to, post_data["reply_to"])
    self.assertEquals(messages[2].subject, post_data["subject"])
    self.assertEquals(type(model.Pledge.all()[0].thank_you_sent_at), datetime.datetime)
    resp_data = json.loads(resp.text)
    self.assertEquals(resp_data['num_emailed'], 1)
    self.assertEquals(resp_data['total_pledges'], 1)

    # make sure it isn't sent a message again when new_member is set to true
    post_data['new_members'] = True
    resp = self.app.post('/r/thank', post_data)
    messages = self.mail_stub.get_sent_messages(to=self.pledge["email"])
    self.assertEquals(len(messages), 3)
    resp_data = json.loads(resp.text)
    self.assertEquals(resp_data['num_emailed'], 0)
    self.assertEquals(resp_data['total_pledges'], 1)

  def testUserInfoNotFound(self):
    resp = self.app.get('/user-info/nouserhere', status=404)
    self.assertEquals('user not found', resp.body)

  def testUserInfoNoPledge(self):
    self.makeDefaultRequest()
    self.assertEquals(1, model.Pledge.all().count())
    user = model.User.get_by_key_name('pika@pokedex.biz')
    model.Pledge.all().filter('email =', user.email)[0].delete()
    resp = self.app.get('/user-info/%s' % user.url_nonce, status=404)
    self.assertEquals('user not found', resp.body)

  def testNoPledgeType(self):
    del self.pledge['pledgeType']
    resp = self.makeDefaultRequest()
    pledge = db.get(resp.json['id'])
    self.assertEquals('CONDITIONAL', pledge.pledge_type)

  def testDonation(self):
    self.pledge['pledgeType'] = 'DONATION'
    resp = self.makeDefaultRequest()
    pledge = db.get(resp.json['id'])
    self.assertEquals('DONATION', pledge.pledge_type)

  def testBadType(self):
    self.pledge['pledgeType'] = 'ALL_FOR_ME'
    self.app.post_json('/r/pledge', self.pledge, status=400)

  def testReceipt_404(self):
    self.app.get('/receipt/foobar', status=404)

  def testReceipt_403(self):
    resp = self.makeDefaultRequest()
    self.app.get('/receipt/' + resp.json['id'], status=403)
    self.app.get('/receipt/%s?auth_token=%s' % (resp.json['id'], 'foobar'),
                 status=403)

  # TODO(hjfreyer): Re-enable this test. At the moment it fails because the path
  # isn't right, and it can't get at the template it needs.
  #
  # def testReceipt_200(self):
  #   resp = self.makeDefaultRequest()
  #   self.app.get('/receipt/%s?auth_token=%s' % (resp.json['id'],
  #                                               resp.json['auth_token']))

  # def testBitcoinStart(self):
  #   Need to stub URL fetch and return the expected dictionary

  #   secret = model.Secrets.get()
  #   secret.bitpay_api_key = '123432432'
  #   secret.put()

  #   fetch_stub = self.testbed.get_stub('urlfetch')
  #   return = {'status': 'new', 'invoiceTime': 1393950046292, 'currentTime': 1393950046520, 'url': 'https://bitpay.com/invoice?id=aASDF2jh4ashkASDfh234', 'price': 1, 'btcPrice': '1.0000', 'currency': 'BTC', 'posData': '{"posData": "fish", "hash": "ASDfkjha452345ASDFaaskjhasdlfkflkajsdf"}', 'expirationTime': 1393950946292, 'id': 'aASDF2jh4ashkASDfh234'}

  #   self.pledge['payment'] = {'BITPAY': {}}
  #   resp = self.app.post_json('/r/bitcoin_start', self.pledge)
  #   self.assertEqual(model.TempPledge.all().count(), 1)
  #   temp_pledge = model.TempPledge.all()[0]
  #   self.assertEqual(temp_pledge.name, self.pledge["name"])
  #   self.assertEqual(temp_pledge.team, self.pledge["team"])
  #   self.assertEqual(temp_pledge.amountCents, self.pledge["amountCents"])
  #   self.assertEqual(temp_pledge.subscribe, self.pledge["subscribe"])


  def testBitpayNotifications(self):
    self.expectSubscribe()
    self.mockery.ReplayAll()

    temp_pledge = model.TempPledge(
      model_version=model.MODEL_VERSION,
      email=self.pledge["email"],
      phone=self.pledge["phone"],
      name=self.pledge["name"],
      firstName=u'Pik\u00E1',
      lastName=u'Chu',
      occupation=self.pledge["occupation"],
      employer=self.pledge["employer"],
      subscribe=True,
      amountCents=4200,
      )
    temp_key = temp_pledge.put()
    temp_key_str = str(temp_key)

    notification = {'status': 'confirmed', 'url': 'https://bitpay.com/invoice?id=aASDF2jh4ashkASDfh234',
      'price': 42, 'btcPrice': '1.0000', 'currency': 'BTC', 'posData': temp_key_str,
      'expirationTime': 1393950946292, 'id': 'aASDF2jh4ashkASDfh234'}
    resp = self.app.post_json('/r/bitcoin_notifications', notification)
    # import pdb; pdb.set_trace()
