import unittest
import logging
#from datetime import datetime, timedelta

#from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed

import model

class TestConfig(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

class TestSecrets(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

class TestUser(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

  def test_createOrUpdate(self):
    '''Create or Update a User'''
    fake_email = 'john@smith.com'
    fake_stripe_id = 'should there be a test ID for proper testing?'
    fake_occupation = 'Lobbyist'
    fake_employer = 'Acme'
    fake_phone = '800-555-1212'
    fake_target = None

    logging.info('Testing updating a user that does not exist...')

    user0 = model.User.createOrUpdate(
      email=fake_email,
      occupation = fake_occupation,
      employer = fake_employer,
      phone= fake_phone )

    self.assertEqual(user0.email, fake_email)
    self.assertEqual(user0.occupation, fake_occupation)
    self.assertEqual(user0.employer, fake_employer)
    self.assertEqual(user0.phone, fake_phone)

    logging.info('Test updating that user we just created...')
    user1 = model.User.createOrUpdate(email=fake_email, occupation='Regulator')
    self.assertEqual(user1.occupation, 'Regulator')

    #TODO: confirm storage in datastore.
    #TODO: see if we can store bad emails and other data


class TestPledge(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

class TestWpPledge(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

class TestShardedCounter(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

class TestFunctions(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()
