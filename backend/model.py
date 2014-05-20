import json
import logging
import os
import random

from collections import namedtuple

from google.appengine.ext import db

import cache

class Error(Exception): pass

# Used to indicate which data objects were created in which version of
# the app, in case we need to special-case some logic for objects
# which came before a certain point.
#
# Versions:
#   <missing>: Initial model.
#   2: Implemented sharded counter for donation total. Objects before
#      this version are not included in that counter.
MODEL_VERSION = 2


# Config singleton. Loaded once per instance and never modified. It's
# okay if try to load it multiple times, so no worries about race
# conditions.
#
# Note that this isn't really a "model", it's built up from config.json
# and the "Secrets" model.
class Config(object):
  ConfigType = namedtuple('ConfigType',
                          ['app_name',
                           'stripe_public_key', 'stripe_private_key'])
  _instance = None

  @staticmethod
  def get():
    if Config._instance:
      return Config._instance

    j = json.load(open('config.json'))
    s = Secrets.get()

    if 'hardCodeStripe' in j:
      stripe_public_key = j['stripePublicKey']
      stripe_private_key = j['stripePrivateKey']
    elif s:
      stripe_public_key = s.stripe_public_key
      stripe_private_key = s.stripe_private_key
    else:      # If the secrets haven't been loaded yet, omit them.
      stripe_public_key = None
      stripe_private_key = None

    Config._instance = Config.ConfigType(
      app_name = j['appName'],
      stripe_public_key=stripe_public_key,
      stripe_private_key=stripe_private_key)
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
  model_version = db.IntegerProperty()

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
    pledge = Pledge(model_version=MODEL_VERSION,
                    email=email,
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


SHARD_KEY_TEMPLATE = 'shard-{}-{:d}'
SHARD_COUNT = 50

class ShardedCounter(db.Model):
  count = db.IntegerProperty(default=0)

  @staticmethod
  def get_count(name):
    total = cache.GetShardedCounterTotal(name)
    if total is None:
      total = 0
      all_keys = ShardedCounter._get_keys_for(name)
      for counter in db.get(all_keys):
        if counter is not None:
          total += counter.count
      logging.info("recalculated counter %s to %s", name, total)
      cache.SetShardedCounterTotal(name, total)
    return total

  @staticmethod
  def _get_keys_for(name):
    shard_key_strings = [SHARD_KEY_TEMPLATE.format(name, index)
                         for index in range(SHARD_COUNT)]
    return [db.Key.from_path('ShardedCounter', shard_key_string)
            for shard_key_string in shard_key_strings]

  @staticmethod
  @db.transactional
  def increment(name, delta):
    index = random.randint(0, SHARD_COUNT - 1)
    shard_key_string = SHARD_KEY_TEMPLATE.format(name, index)
    counter = ShardedCounter.get_by_key_name(shard_key_string)
    if counter is None:
      counter = ShardedCounter(key_name=shard_key_string)
    counter.count += delta
    counter.put()

    # TODO(hjfreyer): Enable memcache increments.
    #
    # Memcache increment does nothing if the name is not a key in memcache
    # memcache.incr(ShardedCounter._get_memcache_key(name), delta=delta)

def increment_donation_total(amount):
  ShardedCounter.increment('TOTAL', amount)


# SECONDARY MODELS
# ################
# These models are used as caches for other parts of the data model,
# and should always be regenerable. Do not make these the single
# source of truth for anything!

# Generated by commands.FindMissingDataUsers.
class MissingDataUsersSecondary(db.Model):
  email = db.EmailProperty(required=True)

  # amountCents never needs to be recomputed. The only way it can
  # change is to go up, and if it does, it means the user pledged
  # again, so they must have filled in their missing data.
  amountCents = db.IntegerProperty(required=True)
