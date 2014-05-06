import logging
import os

from collections import namedtuple

from google.appengine.ext import db

class Error(Exception): pass


# Config singleton. Loaded once per instance and never modified. It's
# okay if try to load it multiple times, so no worries about race
# conditions.
class Config(object):
  ConfigType = namedtuple('ConfigType',
                          ['stripe_public_key', 'stripe_private_key'])
  _instance = None

  @staticmethod
  def get():
    if Config._instance:
      return Config._instance

    s = Secrets.get()
    Config._instance = Config.ConfigType(
      # If the secrets haven't been loaded yet, omit them.
      stripe_public_key=s.stripe_public_key if s else None,
      stripe_private_key=s.stripe_private_key if s else None)
    return Config._instance


# Secrets to store in the DB, rather than git.
class Secrets(db.Model):
  # We include the public key so they're never out of sync.
  stripe_public_key = db.StringProperty(required=True)
  stripe_private_key = db.StringProperty(required=True)

  @staticmethod
  def get():
    s = list(Secrets.all())
    if len(s) > 1:
      raise Error('Have multiple secrets in the database somehow. This '
                  "shouldn't happen.")
    return s[0] if s else None

  @staticmethod
  def update(stripe_public_key, stripe_private_key):
    if list(Secrets.all()):
      raise Error('DB already contains secrets. Delete them first')
    s = Secrets(stripe_public_key=stripe_public_key,
                stripe_private_key=stripe_private_key)
    s.put()


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

  from_import = db.BooleanProperty(required=False)

  @staticmethod
  @db.transactional
  def createOrUpdate(email, occupation=None, employer=None, phone=None,
                     target=None, from_import=None):
    user = User.get_by_key_name(email)
    if user is None:
      user = User(key_name=email,
                  email=email,
                  url_nonce=os.urandom(32).encode("hex"),
                  from_import=from_import)
    if occupation is not None:
      if not from_import or user.occupation is None:
          user.occupation = occupation
    if employer is not None:
      if not from_import or user.employer is None:
        user.employer = employer
    if phone is not None:
      if not from_import or user.phone is None:
        user.phone = phone
    if target is not None:
      if not from_import or user.target is None:
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


class WpPledge(db.Model):
  # wp_post_id is also the model key
  wp_post_id = db.IntegerProperty(required=True)

  email = db.EmailProperty(required=True)
  stripeCustomer = db.StringProperty(required=True)
  amountCents = db.IntegerProperty(required=True)
  donationTime = db.DateTimeProperty(required=True)

  occupation = db.StringProperty(required=False)
  employer = db.StringProperty(required=False)
  phone = db.StringProperty(required=False)
  target = db.StringProperty(required=False)

  url_nonce = db.StringProperty(required=True)
