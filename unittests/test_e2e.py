import unittest
import logging
import datetime

from google.appengine.ext import db
from google.appengine.ext import testbed
import mox
import webapp2
import webtest

from backend import handlers
from backend import model


class BaseTest(unittest.TestCase):
  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()

    self.testbed.init_datastore_v3_stub()

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
  def samplePledge(self):
    return dict(
      email='pika@pokedex.biz',
      phone='212-234-5432',
      name=u'Pik\u00E1 Chu',
      occupation=u'Pok\u00E9mon',
      employer='Nintendo',
      target='Republicans Only',
      subscribe=True,
      amountCents=4200,
      payment=dict(
        STRIPE=dict(
          token='tok_1234',
        )
      ))

  def testBadJson(self):
    self.app.post('/r/pledge', '{foo', status=400)

  def testNotEnoughJson(self):
    self.app.post_json('/r/pledge', dict(email='foo@bar.com'), status=400)

  def testCreateAddsPledge(self):
    self.stripe.CreateCustomer(email='pika@pokedex.biz',
                               card_token='tok_1234') \
               .AndReturn('cust_4321')

    self.mailing_list_subscriber \
        .Subscribe(email='pika@pokedex.biz',
                   first_name=u'Pik\u00E1', last_name='Chu',
                   amount_cents=4200, ip_addr=None,  # Not sure why this is None
                                                     # in unittests.
                   time=mox.IsA(datetime.datetime), source='pledged')

    self.mail_sender.Send(to=mox.IsA(str), subject=mox.IsA(str),
                          text_body=mox.IsA(str),
                          html_body=mox.IsA(str))

    self.mockery.ReplayAll()

    resp = self.app.post_json('/r/pledge', self.samplePledge())

    pledge = db.get(resp.json['id'])
    self.assertEquals(4200, pledge.amountCents)
    self.assertEquals(resp.json['auth_token'], pledge.url_nonce)
    self.assertEquals('cust_4321', pledge.stripeCustomer)

    user = model.User.get_by_key_name('pika@pokedex.biz')

    sample = self.samplePledge()
    def assertEqualsSampleProperty(prop_name, actual):
      self.assertEquals(sample[prop_name], actual)
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
    self.stripe.CreateCustomer(email='pika@pokedex.biz',
                               card_token='tok_1234') \
               .AndReturn('cust_4321')

    self.mailing_list_subscriber \
        .Subscribe(email='pika@pokedex.biz',
                   first_name=u'Pik\u00E1', last_name='Chu',
                   amount_cents=4200, ip_addr=None,  # Not sure why this is None
                                                     # in unittests.
                   time=mox.IsA(datetime.datetime), source='pledged')

    self.mail_sender.Send(to=mox.IsA(str), subject=mox.IsA(str),
                          text_body=mox.IsA(str),
                          html_body=mox.IsA(str))

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', self.samplePledge())
    user = model.User.get_by_key_name('pika@pokedex.biz')
    assert user.mail_list_optin

  def testSubscribeOptOut(self):
    sample = self.samplePledge()
    sample['subscribe'] = False

    self.stripe.CreateCustomer(email='pika@pokedex.biz',
                               card_token='tok_1234') \
               .AndReturn('cust_4321')

    self.mail_sender.Send(to=mox.IsA(str), subject=mox.IsA(str),
                          text_body=mox.IsA(str),
                          html_body=mox.IsA(str))

    # Don't subscribe.

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', sample)
    user = model.User.get_by_key_name('pika@pokedex.biz')
    assert not user.mail_list_optin

  def testNoPhone(self):
    sample = self.samplePledge()
    sample['phone'] = ''

    self.stripe.CreateCustomer(email='pika@pokedex.biz',
                               card_token='tok_1234') \
               .AndReturn('cust_4321')

    self.mailing_list_subscriber \
        .Subscribe(email='pika@pokedex.biz',
                   first_name=u'Pik\u00E1', last_name='Chu',
                   amount_cents=4200, ip_addr=None,  # Not sure why this is None
                                                     # in unittests.
                   time=mox.IsA(datetime.datetime), source='pledged')

    self.mail_sender.Send(to=mox.IsA(str), subject=mox.IsA(str),
                          text_body=mox.IsA(str),
                          html_body=mox.IsA(str))

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', sample)

  def testNoName(self):
    sample = self.samplePledge()
    sample['name'] = ''

    self.mockery.ReplayAll()

    self.app.post_json('/r/pledge', sample, status=400)

  def testMail(self):
    sample = self.samplePledge()
    sample['subscribe'] = False

    self.stripe.CreateCustomer(email='pika@pokedex.biz',
                               card_token='tok_1234') \
               .AndReturn('cust_4321')

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

    self.app.post_json('/r/pledge', sample)
