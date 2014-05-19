import unittest
import logging
#from datetime import datetime, timedelta

#from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from backend import main

class TestGetTotalHandler(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()
    
class TestGetStripePublicKeyHandler(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

class TestEmbedHandler(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()

class TestPledgeHandler(unittest.TestCase):
  def setUp(self):
    # First, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed, which prepares the service stubs for use.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.#self.testbed.init_datastore_v3_stub()
    self.testbed.init_urlfetch_stub()

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
