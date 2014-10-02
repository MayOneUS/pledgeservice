"""Environment params and backend implementations."""

import json
import logging
import datetime

from rauth import OAuth2Service

from google.appengine.api import mail
from google.appengine.ext import deferred
from mailchimp import mailchimp
import stripe

import handlers
import model


def get_env():
  """Get environmental parameters."""
  j = json.load(open('config.json'))

  stripe_backend = None
  mailing_list_subscriber = None
  if j['appName'] == 'local':
    stripe_backend = FakeStripe()
    mailing_list_subscriber = FakeSubscriber()
  else:
    stripe_backend = ProdStripe(model.Config.get().stripe_private_key)
    mailing_list_subscriber = MailchimpSubscriber()

  return handlers.Environment(
    app_name=j['appName'],
    stripe_public_key=model.Config.get().stripe_public_key,
    stripe_backend=stripe_backend,
    mailing_list_subscriber=mailing_list_subscriber,
    mail_sender=MailSender())


class ProdStripe(handlers.StripeBackend):
  def __init__(self, stripe_private_key):
    self.stripe_private_key = stripe_private_key

  def CreateCustomer(self, email, card_token):
    stripe.api_key = self.stripe_private_key
    customer = stripe.Customer.create(card=card_token, email=email)
    return customer

  def RetrieveCardData(self, customer_id):
    stripe.api_key = self.stripe_private_key
    cus = stripe.Customer.retrieve(customer_id)
    return cus.cards.data[0] if len(cus.cards.data) > 0 else {}

  def Charge(self, customer_id, amount_cents):
    stripe.api_key = self.stripe_private_key
    try:
      charge = stripe.Charge.create(
        amount=amount_cents,
        currency='usd',
        customer=customer_id,
        statement_description='MayOne.US',
      )
    except stripe.CardError, e:
      logging.info('Stripe returned error for customer: %s ' % customer_id)
      raise handlers.PaymentError(str(e))
    return charge.id


class FakeStripe(handlers.StripeBackend):
  def CreateCustomer(self, email, card_token):
    logging.warning('USING FAKE STRIPE')
    cus = stripe.Customer()
    cus.cards = stripe.ListObject()
    if email == 'failure@failure.biz':
      cus.id = 'doomed_customer'
      cus.cards.data = []
    else:
      cus.id = 'fake_1234'
      cus.cards.data = [self.RetrieveCardData(id)]
    return cus

  def RetrieveCardData(self, customer_id):
    return {
      "address_city": "Washington",
      "address_country": "US",
      "address_line1": "1600 Pennsylvania Ave NW",
      "address_line1_check": "pass",
      "address_line2": "",
      "address_state": "DC",
      "address_zip": "20500",
      "address_zip_check": "pass",
      "brand": "Visa",
      "country": "US",
      "customer": customer_id,
      "cvc_check": "pass",
      "exp_month": 3,
      "exp_year": 2020,
      "fingerprint": "fakefingerprint",
      "funding": "debit",
      "id": "card_fakeid",
      "last4": "4242",
      "name": "Phillip Mamouf-Wifarts",
      "object": "card",
      "type": "Visa"
    }

  def Charge(self, customer_id, amount_cents):
    logging.error('USING FAKE STRIPE')
    if customer_id == 'doomed_customer':
      raise handlers.PaymentError(
        'You have no chance to survive make your time')
    logging.error('CHARGED CUSTOMER %s %d cents', customer_id, amount_cents)
    return 'fake_charge_1234'


class MailchimpSubscriber(handlers.MailingListSubscriber):
  def Subscribe(self, email, first_name, last_name, amount_cents, ip_addr, time,
                source, phone=None, zipcode=None, volunteer=None, skills=None, rootstrikers=None,
                nonce=None, pledgePageSlug=None, otherVars = None):
    #deferred.defer(_subscribe_to_mailchimp,
    #               email, first_name, last_name,
    #               amount_cents, ip_addr, source, phone, zipcode,
    #               volunteer, skills, rootstrikers, 
    #               nonce, pledgePageSlug, otherVars)
    deferred.defer(_subscribe_to_nationbuilder,
                   email, first_name, last_name,
                   amount_cents, ip_addr, source, phone, zipcode,
                   volunteer, skills, rootstrikers,
                   nonce, pledgePageSlug, otherVars)

class FakeSubscriber(handlers.MailingListSubscriber):
  def Subscribe(self, **kwargs):
    logging.info('Subscribing %s', kwargs)


class MailSender(object):
  def __init__(self, defer=True):
    # this can
    self.defer = defer

  def Send(self, to, subject, text_body, html_body, reply_to=None):
    if self.defer:
      deferred.defer(_send_mail, to, subject, text_body, html_body, reply_to)
    else:
      _send_mail(to, subject, text_body, html_body, reply_to)


def _send_mail(to, subject, text_body, html_body, reply_to=None):
  """Deferred email task"""
  sender = ('Mayday PAC <noreply@%s.appspotmail.com>' %
            model.Config.get().app_name)
  message = mail.EmailMessage(sender=sender, subject=subject)
  message.to = to
  message.body = text_body
  message.html = html_body
  if reply_to:
    message.reply_to = reply_to
  else:
    message.reply_to = 'info@mayday.us'
  message.send()

def _subscribe_to_nationbuilder(email_to_subscribe, first_name, last_name,
                            amount, request_ip, source, phone=None, zipcode=None,
                            volunteer=None, skills=None, rootstrikers=None,
                            nonce=None, pledgePageSlug=None, otherVars=None):
  nationbuilder_token = model.Secrets.get().nationbuilder_token
  nation_slug = "mayday"
  access_token_url = "http://" + nation_slug + ".nationbuilder.com/oauth/token"
  authorize_url = nation_slug + ".nationbuilder.com/oauth/authorize"
  service = OAuth2Service(
    client_id = "c2803fd687f856ce94a55b7f66121c79b75bf7283c467c855e82d53af07074e9",
    client_secret = "0d133e9f2b24ab3b897b4a9a216a1a8391a67b96805eb9a3c9305c0f7ac0e411",
    name = "anyname",
    authorize_url = authorize_url,
    access_token_url = access_token_url,
    base_url = nation_slug + ".nationbuilder.com")
  session = service.get_session(nationbuilder_token)
  person = {'email':email_to_subscribe, 
        'first_name':first_name,
        'last_name':last_name,
        'request_ip':request_ip
  }
  if rootstrikers:
    person["rootstrikers_subscription"] = rootstrikers
  
  if volunteer:
    person["volunteer"] = volunteer

  if phone:
    person["phone"] = phone

  if zipcode:
    person['primary_address'] = {'zip':zipcode}

  if skills:
    person['skills'] = skills

  if nonce:
    person['uuid'] = nonce

  if pledgePageSlug:
    person['pledge_page_slug'] = pledge_page_slug

  if otherVars:
    merge13 = otherVars.get('MERGE13', '')
    if merge13 != '':
      person['fundraising_email_subscription'] = merge13

  response = session.put('https://' + nation_slug +".nationbuilder.com/api/v1/people/push",
    data=json.dumps({'person':person}),
    headers={"content-type":"application/json"}
  )
  id = json.loads(response.content)["person"]["id"]
  response = session.put('https://' + nation_slug + ".nationbuilder.com/api/v1/people/" + str(id) + "/taggings",
    data=json.dumps({"tagging":{"tag":"source: " + source}}),
    headers={"content-type":"application/json"}
  )

def _subscribe_to_mailchimp(email_to_subscribe, first_name, last_name,
                            amount, request_ip, source, phone=None, zipcode=None,
                            volunteer=None, skills=None, rootstrikers=None,
                            nonce=None, pledgePageSlug=None, otherVars=None):
  mailchimp_api_key = model.Config.get().mailchimp_api_key
  mailchimp_list_id = model.Config.get().mailchimp_list_id


  mc = mailchimp.Mailchimp(mailchimp_api_key)
  merge_vars = {
    'FNAME': first_name,
    'LNAME': last_name,
    'optin_ip': request_ip,
    'optin_time': str(datetime.datetime.now())
  }

  if source:
    merge_vars['SOURCE'] = source

  if amount:
    amount_dollars = '{0:.02f}'.format(float(amount) / 100.0)
    merge_vars['LASTPLEDGE'] = amount_dollars

  if volunteer == 'Yes':
    merge_vars['VOLN'] = volunteer

  if nonce is not None:
    merge_vars['UUT'] = nonce

  if skills is not None and len(skills)>0:
    merge_vars['SKILLS'] = skills[0:255]

  if phone is not None:
    merge_vars['PHONE'] = phone

  if zipcode is not None:
    merge_vars['ZIP'] = zipcode

  if rootstrikers is not None:
    merge_vars['ROOTS'] = rootstrikers

  if pledgePageSlug is not None:
    merge_vars['PPURL'] = pledgePageSlug
    
  if otherVars is not None:
    merge_vars.update(otherVars)

  # list ID and email struct
  logging.info('Subscribing: %s. Merge_vars: %s', email_to_subscribe, str(merge_vars))
  mc.lists.subscribe(id=mailchimp_list_id,
                     email=dict(email=email_to_subscribe),
                     merge_vars=merge_vars,
                     double_optin=False,
                     update_existing=True,
                     send_welcome=False)
