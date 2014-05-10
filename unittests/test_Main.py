import unittest
import logging
#from datetime import datetime, timedelta

#from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from backend import main

class TestUser(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.#self.testbed.init_datastore_v3_stub()
    #self.testbed.init_memcache_stub()
    #self.testbed.init_urlfetch_stub()

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
    
    user0 = main.User()
    user0.createOrUpdate(
      email=fake_email, 
      occupation = fake_occupation, 
      employer = fake_employer, 
      phone= fake_phone )
      
    self.assertEqual(user0.email, fake_email)
    self.assertEqual(user0.occupation, fake_occupation)
    self.assertEqual(user0.employer, fake_employer)
    self.assertEqual(user0.phone, fake_phone)
    
    logging.info('Test updating that user we just created...')
    user1 = main.User()
    user1.createOrUpdate(email=fake_email, fake_occupation='Regulator')
    self.assertEqual(user1.fake_occupation, 'Regulator')
    
    #TODO: confirm storage in datastore.


class TestPledge(unittest.TestCase):
    def setUp(self):
      # First, create an instance of the Testbed class.
      self.testbed = testbed.Testbed()
      # Then activate the testbed, which prepares the service stubs for use.
      self.testbed.activate()
      # Next, declare which service stubs you want to use.#self.testbed.init_datastore_v3_stub()
      #self.testbed.init_memcache_stub()
      #self.testbed.init_urlfetch_stub()

    def tearDown(self):
      self.testbed.deactivate()
     
    def test_create(self):
      self.fail('TEST NOT IMPLEMENTED')

    def test_importOrUpdate(self):
      self.fail('TEST NOT IMPLEMENTED')

class TestFunctions(unittest.TestCase):
    def setUp(self):
      # First, create an instance of the Testbed class.
      self.testbed = testbed.Testbed()
      # Then activate the testbed, which prepares the service stubs for use.
      self.testbed.activate()
      # Next, declare which service stubs you want to use.#self.testbed.init_datastore_v3_stub()
      #self.testbed.init_memcache_stub()
      #self.testbed.init_urlfetch_stub()

    def tearDown(self):
      self.testbed.deactivate()

    def test_addPledge(self):
      self.fail('TEST NOT IMPLEMENTED')

    def test_importPledge(self):
      self.fail('TEST NOT IMPLEMENTED')
