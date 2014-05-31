import unittest
import logging
import datetime

from google.appengine.ext import db
from google.appengine.ext import testbed
import mox
import webapp2
import webtest

import handlers
import model


class BaseTest(unittest.TestCase):
  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()

    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()

    self.mockery = mox.Mox()
    self.stripe = self.mockery.CreateMock(handlers.StripeBackend)
    self.mailing_list_subscriber = self.mockery.CreateMock(
      handlers.MailingListSubscriber)
    self.mail_sender = self.mockery.CreateMock(handlers.MailSender)

    self.env = handlers.Environment(
      app_name='unittest',
      stripe_public_key='pubkey1234',
      stripe_backend=self.stripe,
      mailing_list_subscriber=self.mailing_list_subscriber,
      mail_sender=self.mail_sender)
    self.wsgi_app = webapp2.WSGIApplication(handlers.HANDLERS,
                                            config=dict(env=self.env))

    self.app = webtest.TestApp(self.wsgi_app)

  def tearDown(self):
    self.mockery.VerifyAll()
    self.testbed.deactivate()


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
      team='rocket',
      payment=dict(
        STRIPE=dict(
          token='tok_1234',
        )
      ))

    handlers.TotalHandler.PRE_SHARDING_TOTAL = 10
    handlers.TotalHandler.WP_PLEDGE_TOTAL = 11
    handlers.TotalHandler.DEMOCRACY_DOT_COM_BALANCE = 12
    handlers.TotalHandler.CHECKS_BALANCE = 13

    self.balance_baseline = 46

  def expectStripe(self):
    self.stripe.CreateCustomer(
      email=self.pledge['email'],
      card_token=self.pledge['payment']['STRIPE']['token']) \
               .AndReturn('cust_4321')

  def expectSubscribe(self):
    self.mailing_list_subscriber \
        .Subscribe(email=self.pledge['email'],
                   first_name=u'Pik\u00E1',
                   last_name='Chu',
                   amount_cents=4200, ip_addr=None,  # Not sure why this is None
                                                     # in unittests.
                   time=mox.IsA(datetime.datetime), source='pledged')

  def expectMailSend(self):
    self.mail_sender.Send(to=mox.IsA(str), subject=mox.IsA(str),
                          text_body=mox.IsA(str),
                          html_body=mox.IsA(str))

  def makeDefaultRequest(self):
    self.expectStripe()
    self.expectSubscribe()
    self.expectMailSend()
    self.mockery.ReplayAll()

    return self.app.post_json('/r/pledge', self.pledge)

  def testBadJson(self):
    self.app.post('/r/pledge', '{foo', status=400)

  def testNotEnoughJson(self):
    self.app.post_json('/r/pledge', dict(email='foo@bar.com'), status=400)

  def testCreateAddsPledge(self):
    resp = self.makeDefaultRequest()
    pledge = db.get(resp.json['id'])
    self.assertEquals(4200, pledge.amountCents)
    self.assertEquals(resp.json['auth_token'], pledge.url_nonce)
    self.assertEquals('cust_4321', pledge.stripeCustomer)
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

  def testSubscribes(self):
    self.expectStripe()
    self.expectSubscribe()
    self.expectMailSend()

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', self.pledge)
    user = model.User.get_by_key_name('pika@pokedex.biz')
    assert user.mail_list_optin

  def testSubscribeOptOut(self):
    self.pledge['subscribe'] = False

    self.expectStripe()
    self.expectMailSend()

    # Don't subscribe.

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', self.pledge)
    user = model.User.get_by_key_name('pika@pokedex.biz')
    assert not user.mail_list_optin

  def testNoPhone(self):
    self.pledge['phone'] = ''
    self.makeDefaultRequest()

  def testNoName(self):
    self.pledge['name'] = ''

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', self.pledge, status=400)

  def testMail(self):
    self.pledge['subscribe'] = False

    self.expectStripe()

    self.mail_sender.Send(to='pika@pokedex.biz', subject='Thank you for your pledge',
                          text_body="""Dear Pik\xc3\xa1 Chu:

Thank you for your pledge to the MaydayPAC. We are grateful for the support to make it possible for us to win back our democracy.

But may I ask for one more favor?

We will only win if we find 100 people for every person like you. It would be incredibly helpful if you could help us recruit them, ideally by sharing the link to the MayOne.US site. We've crafted something simple to copy and paste below. Or you can like us on our Facebook Page[1], or follow @MayOneUS[2] on Twitter.

We'd be grateful for your feedback and ideas for how we can spread this message broadly. We're watching the social media space for #MaydayPAC, or you can email your ideas to info@mayone.us.

This is just the beginning. But if we can succeed as we have so far, then by 2016, we will have taken the first critical step to getting our democracy back.

This email serves as your receipt for your pledge of: $42

Thank you again,

Lessig
lessig@mayone.us

Suggested text:

I just supported a SuperPAC to end all SuperPACs \xe2\x80\x94 the #MaydayPAC, citizen-funded through a crowd-funded campaign. You can check it out here: http://mayone.us.

[1] https://www.facebook.com/mayonedotus
[2] https://twitter.com/MayOneUS

----------------------
Paid for by MayDay PAC
Not authorized by any candidate or candidate\xe2\x80\x99s committee
www.MayOne.us
""",
                          html_body='''<html>
  <body>
    <p>Dear Pik\xc3\xa1 Chu,</p>

    <p>Thank you for your pledge to the MaydayPAC. We are grateful for the support to make it possible for us to win back our democracy.</p>

    <p>But may I ask for one more favor?</p>

    <p>We will only win if we find 100 people for every person like you. It would be incredibly helpful if you could help us recruit them, ideally by sharing the link to the MayOne.US site. We\'ve crafted something simple to copy and paste below. Or you can like us on <a href="https://www.facebook.com/mayonedotus">our Facebook Page</a>, or follow <a href="https://twitter.com/MayOneUS">@MayOneUS</a> on Twitter.</p>

    <p>We\'d be grateful for your feedback and ideas for how we can spread this message broadly. We\'re watching the social media space for #MaydayPAC, or you can email your ideas to <a href="mailto:info@mayone.us">info@mayone.us</a>.</p>

    <p>This is just the beginning. But if we can succeed as we have so far, then by 2016, we will have taken the first critical step to getting our democracy back.</p>

    <p>This email serves as your receipt for your pledge of: $42</p>

    <p>Thank you again,</p>

    <p>
       Lessig<br/>
       lessig@mayone.us
    </p>

    <p>Suggested text:</p>
    <p>I just supported a SuperPAC to end all SuperPACs &ndash; the #MaydayPAC, citizen-funded through a crowd-funded campaign. You can check it out here: http://mayone.us.</p>

    <p>
      ----------------------<br/>
      Paid for by MayDay PAC<br/>
      Not authorized by any candidate or candidate\xe2\x80\x99s committee<br/>
      www.MayOne.us
    </p>
  </body>
</html>
''')

    # Don't subscribe.

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', self.pledge)

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
      self.expectMailSend()
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
