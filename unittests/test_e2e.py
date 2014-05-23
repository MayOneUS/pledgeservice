import unittest
import logging
#from datetime import datetime, timedelta

#from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed

import webtest
import webapp2
from backend import handlers
from backend import model

class BaseTest(unittest.TestCase):
  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()

    self.testbed.init_datastore_v3_stub()

    self.app = webtest.TestApp(webapp2.WSGIApplication(handlers.HANDLERS))

  def tearDown(self):
     self.testbed.deactivate()

class PledgeTest(BaseTest):
  SAMPLE_USER = dict(
    email='pika@pokedex.biz',
    phone='212-234-5432',
    firstName='Pika',
    lastName='Chu',
    occupation=u'Pok\u00E9mon',
    employer='Nintendo',
    target='Republicans Only',
    subscribe=False,
    amountCents=4200)

  def testBadJson(self):
    self.app.post('/r/pledge', '{foo', status=400)

  def testNotEnoughJson(self):
    self.app.post_json('/r/pledge', dict(email='foo@bar.com'), status=400)

  def testCreateAddsPledge(self):
    resp = self.app.post_json('/r/pledge', PledgeTest.SAMPLE_USER)

    pledge = model.Pledge.get_by_key_name(resp.json['id'])
    self.assertIsNotNone(pledge)
