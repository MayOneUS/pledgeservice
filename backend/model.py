import logging
import os

from google.appengine.ext import db


class User(db.Model):
  # a user's email is also the model key
  email = db.EmailProperty(required=True)

  # occupation and employer are logically required for all new users, but we
  # don't have this data for everyone. so from a data model perspective, they
  # aren't required.
  occupation = db.StringProperty(required=False)
  employer = db.StringProperty(required=False)

  phone = db.StringProperty(required=False)

  # whether or not the pledge was donated specifically for a particular
  # political affiliation
  target = db.StringProperty(required=False)

  # this is the nonce for what we'll put in a url to send to people when we ask
  # them to update their information. it's kind of like their password for the
  # user-management part of the site.
  url_nonce = db.StringProperty(required=True)

  @staticmethod
  @db.transactional
  def createOrUpdate(email, occupation=None, employer=None, phone=None,
                     target=None):
    user = User.get_by_key_name(email)
    if user is None:
      user = User(key_name=email,
                  email=email,
                  url_nonce=os.urandom(32).encode("hex"))
    user.occupation = occupation
    user.employer = employer
    user.phone = phone
    user.target = target
    user.put()
    return user


class Pledge(db.Model):
  # a user's email is also the User model key
  email = db.EmailProperty(required=True)

  # this is the string id for the stripe api to access the customer. we are
  # doing a whole stripe customer per pledge.
  stripeCustomer = db.StringProperty(required=True)

  # when the donation occurred
  donationTime = db.DateTimeProperty(auto_now_add=True)

  # we plan to have multiple fundraising rounds. right now we're in round "1"
  fundraisingRound = db.StringProperty(required=True)

  # what the user is pledging for
  amountCents = db.IntegerProperty(required=True)

  note = db.TextProperty(required=False)

  imported_wp_post_id = db.IntegerProperty(required=False)

  # it's possible we'll want to let people change just their pledge. i can't
  # imagine a bunch of people pledging with the same email address and then
  # getting access to change a bunch of other people's credit card info, but
  # maybe we should support users only changing information relating to a
  # specific pledge. if so, this is their site-management password.
  url_nonce = db.StringProperty(required=True)

  @staticmethod
  def create(email, stripe_customer_id, amount_cents, fundraisingRound="1",
             note=None):
    pledge = Pledge(email=email,
                    stripeCustomer=stripe_customer_id,
                    fundraisingRound=fundraisingRound,
                    amountCents=amount_cents,
                    note=note,
                    url_nonce=os.urandom(32).encode("hex"))
    pledge.put()
    return pledge

  @staticmethod
  @db.transactional
  def importOrUpdate(wp_post_id, email, stripe_customer_id, amount_cents,
                     fundraisingRound="1", note=None):
    pledges = Pledge.all().filter("imported_wp_post_id =", wp_post_id).run(
        limit=1)
    if not pledges:
        pledge = Pledge(url_nonce=os.urandom(32).encode("hex"),
                        imported_wp_post_id=wp_post_id)
    else:
        pledge = pledges[0]
    pledge.email = email
    pledge.stripeCustomer = stripe_customer_id
    pledge.fundraisingRound = fundraisingRound
    pledge.amountCents = amount_cents
    pledge.note = note
    pledge.put()
    return pledge


def addPledge(email, stripe_customer_id, amount_cents, occupation=None,
              employer=None, phone=None, fundraisingRound="1", target=None,
              note=None):
  """Creates a User model if one doesn't exist, finding one if one already
  does, using the email as a user key. Then adds a Pledge to the User with
  the given card token as a new credit card.

  @return: the pledge
  """
  # first, let's find the user by email
  User.createOrUpdate(
          email=email, occupation=occupation, employer=employer, phone=phone,
          target=target)

  return Pledge.create(
          email=email, stripe_customer_id=stripe_customer_id,
          amount_cents=amount_cents, fundraisingRound=fundraisingRound,
          note=note)


def importPledge(wp_post_id, email, stripe_customer_id, amount_cents,
                 occupation=None, employer=None, phone=None,
                 fundraisingRound="1", target=None, note=None):
  User.createOrUpdate(
          email=email, occupation=occupation, employer=employer, phone=phone,
          target=target)
  return Pledge.importOrUpdate(
          wp_post_id=wp_post_id, email=email,
          stripe_customer_id=stripe_customer_id, amount_cents=amount_cents,
          fundraisingRound=fundraisingRound, note=note)
