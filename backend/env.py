"""Environment params and backend implementations."""

import json
import logging
import datetime

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
    mail_sender=ProdMailSender())


class ProdStripe(handlers.StripeBackend):
  def __init__(self, stripe_private_key):
    self.stripe_private_key = stripe_private_key

  def CreateCustomer(self, email, card_token):
    stripe.api_key = self.stripe_private_key
    customer = stripe.Customer.create(card=card_token, email=email)
    return customer.id

  def Charge(self, customer_id, amount_cents):
    stripe.api_key = self.stripe_private_key
    charge = stripe.Charge.create(
      amount=amount_cents,
      currency='usd',
      customer=customer_id,
      statement_description='MayOne.US',
    )
    return charge.id


class FakeStripe(handlers.StripeBackend):
  def CreateCustomer(self, email, card_token):
    logging.error('USING FAKE STRIPE')
    return 'fake_1234'

  def Charge(self, customer_id, amount_cents):
    logging.error('USING FAKE STRIPE')
    logging.error('CHARGED CUSTOMER %s %d cents', customer_id, amount_cents)
    return 'fake_charge_1234'


class MailchimpSubscriber(handlers.MailingListSubscriber):
  def Subscribe(self, email, first_name, last_name, amount_cents, ip_addr, time,
                source, zipcode=None, volunteer=None, skills=None, rootstrikers=None):
    deferred.defer(_subscribe_to_mailchimp,
                   email, first_name, last_name,
                   amount_cents, ip_addr, source, zipcode, volunteer, skills, rootstrikers)


class FakeSubscriber(handlers.MailingListSubscriber):
  def Subscribe(self, **kwargs):
    logging.info('Subscribing %s', kwargs)


class ProdMailSender(handlers.MailSender):
  def Send(self, to, subject, text_body, html_body):
    deferred.defer(_send_mail, to, subject, text_body, html_body)


def _send_mail(to, subject, text_body, html_body):
  """Deferred email task"""
  sender = ('MayOne no-reply <noreply@%s.appspotmail.com>' %
            model.Config.get().app_name)
  message = mail.EmailMessage(sender=sender, subject=subject)
  message.to = to
  message.body = text_body
  message.html = html_body
  message.send()


def _subscribe_to_mailchimp(email_to_subscribe, first_name, last_name,
                            amount, request_ip, source, zipcode=None, volunteer=None, skills=None, rootstrikers=None):
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

  if skills is not None and len(skills)>0:
    merge_vars['SKILLS'] = skills[0:255]

  if zipcode is not None:
    merge_vars['ZIPCODE'] = zipcode
  
  if rootstrikers is not None:
    merge_vars['ROOTS'] = rootstrikers

  # list ID and email struct
  mc.lists.subscribe(id=mailchimp_list_id,
                     email=dict(email=email_to_subscribe),
                     merge_vars=merge_vars,
                     double_optin=False,
                     update_existing=True,
                     send_welcome=False)
