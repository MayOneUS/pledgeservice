import datetime
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
#   3: Include information in the User model including their name and whether
#      they wish to be subscribed to the mailing list.
#   4: Pledges now have "team"s.
#   5: Reset the total sharding counter.
#   6: Pledges now have "pledge_type"s.
#   7: Adds Pledge.stripe_charge. Pledges no longer created without a successful
#      charge. Thus, ChargeStatus is obsolete and deprecated.
#   8: Adds whether or not pledges are anonymous
#   9: Previous versions were not summed on demand into TeamTotal objects.
#      Model 9 and newer pledges are.
MODEL_VERSION = 9


# Config singleton. Loaded once per instance and never modified. It's
# okay if try to load it multiple times, so no worries about race
# conditions.
#
# Note that this isn't really a "model", it's built up from config.json
# and the "Secrets" model.
#
# TODO(hjfreyer): Deprecate this and replace it with handlers.Environment.
class Config(object):
  ConfigType = namedtuple('ConfigType',
                          ['app_name',
                           'stripe_public_key', 'stripe_private_key',
                           'mailchimp_api_key', 'mailchimp_list_id'])
  _instance = None

  @staticmethod
  def get():
    if Config._instance:
      return Config._instance

    j = json.load(open('config.json'))
    s = Secrets.get()

    if j.get('hardCodeStripe'):
      stripe_public_key = j['stripePublicKey']
      stripe_private_key = j['stripePrivateKey']
    else:
      stripe_public_key = s.stripe_public_key
      stripe_private_key = s.stripe_private_key

    Config._instance = Config.ConfigType(
      app_name = j['appName'],
      stripe_public_key=stripe_public_key,
      stripe_private_key=stripe_private_key,
      mailchimp_api_key=s.mailchimp_api_key,
      mailchimp_list_id=s.mailchimp_list_id)
    return Config._instance


# Secrets to store in the DB, rather than git.
#
# If you add a field to this, set the default to the empty string, and then
# after pushing the code, go to /admin and select the "Update Secrets model
# properties" command. Then you should be able to edit the new field in the
# datastore.
class Secrets(db.Model):
  SINGLETON_KEY = 'SINGLETON'

  # We include the public key so they're never out of sync.
  stripe_public_key = db.StringProperty(default='')
  stripe_private_key = db.StringProperty(default='')

  mailchimp_api_key = db.StringProperty(default='')
  mailchimp_list_id = db.StringProperty(default='')

  @staticmethod
  def get():
    return Secrets.get_or_insert(key_name=Secrets.SINGLETON_KEY)

  @staticmethod
  @db.transactional
  def update():
    s = Secrets.get_by_key_name(Secrets.SINGLETON_KEY)
    if s is None:
      s = Secrets(key_name=Secrets.SINGLETON_KEY)
    s.put()


class User(db.Model):
  model_version = db.IntegerProperty()

  # a user's email is also the model key
  email = db.EmailProperty(required=True)

  first_name = db.StringProperty()
  last_name = db.StringProperty()

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

  # whether the user opted in to receive email from us
  mail_list_optin = db.BooleanProperty(required=False)

  @staticmethod
  @db.transactional
  def createOrUpdate(email, first_name=None, last_name=None, occupation=None,
                     employer=None, phone=None, target=None,
                     from_import=None, mail_list_optin=None):
    user = User.get_by_key_name(email)
    if user is None:
      user = User(model_version=MODEL_VERSION,
                  key_name=email,
                  email=email,
                  url_nonce=os.urandom(32).encode("hex"),
                  from_import=from_import,
                  mail_list_optin=mail_list_optin)

    def choose(current, new):
      # If this is an import, current data should win.
      if from_import:
        return current or new
      else:
        return new or current
    user.first_name = choose(user.first_name, first_name)
    user.last_name = choose(user.last_name, last_name)
    user.occupation = choose(user.occupation, occupation)
    user.employer = choose(user.employer, employer)
    user.phone = choose(user.phone, phone)
    user.target = choose(user.target, target)
    user.mail_list_optin = choose(user.mail_list_optin, mail_list_optin)
    user.put()
    return user


class Pledge(db.Model):
  model_version = db.IntegerProperty()

  # a user's email is also the User model key
  email = db.EmailProperty(required=True)

  # this is the string id for the stripe api to access the customer. we are
  # doing a whole stripe customer per pledge.
  stripeCustomer = db.StringProperty(required=True)

  # ID of a successful stripe transaction which occurred prior to creating this
  # pledge.
  stripe_charge_id = db.StringProperty()

  # when the donation occurred
  donationTime = db.DateTimeProperty(auto_now_add=True)

  # we plan to have multiple fundraising rounds. right now we're in round "1"
  fundraisingRound = db.StringProperty()

  # what the user is pledging for
  amountCents = db.IntegerProperty(required=True)

  # Enum for what kind of pledge this is, represented as a string for
  # readability. Valid values are:
  #  - CONDITIONAL: only happens if we meet our goal.
  #  - DONATION: happens regardless
  TYPE_CONDITIONAL = 'CONDITIONAL'
  TYPE_DONATION = 'DONATION'
  TYPE_VALUES = [TYPE_CONDITIONAL, TYPE_DONATION]
  pledge_type = db.StringProperty()

  note = db.TextProperty(required=False)

  # Optionally, a pledge can be assigned to a "team".
  team = db.StringProperty()

  # If anonymous, the pledge shouldn't be displayed along with the user's name
  # publically
  anonymous = db.BooleanProperty(required=False, default=True)

  # it's possible we'll want to let people change just their pledge. i can't
  # imagine a bunch of people pledging with the same email address and then
  # getting access to change a bunch of other people's credit card info, but
  # maybe we should support users only changing information relating to a
  # specific pledge. if so, this is their site-management password.
  url_nonce = db.StringProperty(required=True)

  thank_you_sent_at = db.DateTimeProperty(required=False)

  @staticmethod
  def create(email, stripe_customer_id, stripe_charge_id,
             amount_cents, pledge_type, team, anonymous):
    assert pledge_type in Pledge.TYPE_VALUES
    pledge = Pledge(model_version=MODEL_VERSION,
                    email=email,
                    stripeCustomer=stripe_customer_id,
                    stripe_charge_id=stripe_charge_id,
                    amountCents=amount_cents,
                    pledge_type=pledge_type,
                    team=team,
                    url_nonce=os.urandom(32).encode("hex"),
                    anonymous=anonymous)
    pledge.put()
    TeamTotal.add(team, amount_cents)
    return pledge


class TeamTotal(db.Model):
  # this is also the model key
  team = db.StringProperty(required=True)

  totalCents = db.IntegerProperty(required=False)

  @classmethod
  @db.transactional
  def _create(cls, team_id, pledge_8_count):
    tt = cls.get_by_key_name(team_id)
    if tt is not None:
      return tt
    tt = cls(key_name=team_id, team=team_id, totalCents=pledge_8_count)
    tt.put()
    return tt

  @staticmethod
  def _pledge8Count(team_id):
    """do this outside of a transaction"""
    total = 0
    for pledge in Pledge.all().filter("team =", team_id).filter(
        "model_version <", 9):
      total += pledge.amountCents
    return total

  @classmethod
  def _get(cls, team_id):
    tt = cls.get_by_key_name(team_id)
    if tt is None:
      tt = cls._create(team_id, cls._pledge8Count(team_id))
    return tt

  @classmethod
  def get(cls, team_id):
    return cls._get(team_id).totalCents

  @classmethod
  @db.transactional
  def _add(cls, team_id, amount_cents)
    tt = cls.get_by_key_name(team_id)
    tt.totalCents += amount_cents
    tt.put()

  @classmethod
  def add(cls, team_id, amount_cents):
    # make sure the team total exists first before we add
    cls._get(team_id)
    # okay safe to add
    cls._add(team_id, amount_cents)


def addPledge(email,
              stripe_customer_id, stripe_charge_id,
              amount_cents, pledge_type,
              first_name, last_name, occupation, employer, phone,
              target, team, mail_list_optin, anonymous):
  """Creates a User model if one doesn't exist, finding one if one already
  does, using the email as a user key. Then adds a Pledge to the User with
  the given card token as a new credit card.

  @return: the pledge
  """
  # first, let's find the user by email
  user = User.createOrUpdate(
    email=email, first_name=first_name, last_name=last_name,
    occupation=occupation, employer=employer, phone=phone, target=target,
    mail_list_optin=mail_list_optin)

  return user, Pledge.create(email=email,
                       stripe_customer_id=stripe_customer_id,
                       stripe_charge_id=stripe_charge_id,
                       amount_cents=amount_cents,
                       pledge_type=pledge_type,
                       team=team,
                       anonymous=anonymous)


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


class ChargeStatus(db.Model):
  """Indicates whether a Pledge or WpPledge has been charged or not.

  The key of this model must always be the child of a Pledge or WpPledge, with
  key_name='SINGLETON'.

  When a ChargeStatus is created, it represents permission to execute the charge
  for the parent Pledge or WpPledge. When start_time is set, it indicates that
  some task has attempted to execute that charge. When end_time is set, it
  indicates that the charge was successfully completed, and that information
  about that charge can be found in the other fields.

  If start_time is sufficiently far in the past (10 minutes, say), and end_time
  is as of yet unset, something went wrong which needs to be looked into
  manually.
  """
  SINGLETON_KEY = 'SINGLETON'

  # These three times are as described in the comment above.
  request_time = db.DateTimeProperty(required=True)
  start_time = db.DateTimeProperty()
  end_time = db.DateTimeProperty()

  stripe_charge_id = db.StringProperty()

  @staticmethod
  @db.transactional
  def request(pledge_key):
    """Indicates that we are allowed to execute the charge at our leisure."""
    charge_key = ChargeStatus._get_charge_key(pledge_key)
    pledge = db.get(pledge_key)
    charge_status = db.get(charge_key)

    if not pledge:
      raise Error('No pledge found with key: %s' % pledge_key)

    if charge_status:
      logging.warning('Requesting already requested charge for pledge: %s',
                      pledge_key)
      return

    charge_status = ChargeStatus(key=charge_key,
                                 request_time=datetime.datetime.now())
    charge_status.put()

  @staticmethod
  def execute(stripe_backend, pledge_key):
    """Attempts to execute the charge.

    First, sets the start_time atomically and releases the lock. Then tries to
    charge the user. If successful, sets end_time and the paper trail for the
    charge.
    """
    charge_key = ChargeStatus._get_charge_key(pledge_key)

    # First, indicate that we've started (or bail if someone else already has).
    @db.transactional
    def txn():
      pledge = db.get(pledge_key)
      charge = db.get(charge_key)
      if not pledge:
        raise Error('No pledge found with key: %s' % pledge_key)
      if not charge:
        raise Error('Cannot execute unrequested charge. No status for: %s' %
                    pledge_key)
      if charge.start_time:
        return True, None, None
      else:
        charge.start_time = datetime.datetime.now()
        charge.put()
        return False, pledge, charge

    already_started, pledge, charge = txn()
    if already_started:
      logging.warning('Execution of charge already started for pledge %s',
                      pledge_key)
      return

    # TODO(hjfreyer): Generalize to paypal.
    charge.stripe_charge_id = stripe_backend.Charge(pledge.stripeCustomer,
                                                    pledge.amountCents)
    charge.end_time = datetime.datetime.now()

    # Since we have the lock on this, the transaction should be unnecessary, but
    # let's indulge in a little paranoia.
    @db.transactional
    def txn2():
      charge2 = db.get(charge_key)
      if charge2.end_time:
        raise Error('Lock stolen while executing transaction! Pledge %s' %
                    pledge_key)
      charge.put()
    txn2()

  @staticmethod
  def _get_charge_key(pledge_key):
    return db.Key.from_path('ChargeStatus', ChargeStatus.SINGLETON_KEY,
                            parent=pledge_key)


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

    cache.IncrementShardedCounterTotal(name, delta)


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
