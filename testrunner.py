#!/usr/bin/env python
import os
import sys
import unittest

USAGE = """%prog SDK_PATH TEST_PATH
Run unit tests for App Engine apps."""

SDK_PATH_manual = '/usr/local/google_appengine'
TEST_PATH_manual = '../unittests'

def main(sdk_path, test_path):
  os.chdir('backend')
  sys.path.extend([sdk_path, '.', '../lib', '../testlib'])
  import dev_appserver
  dev_appserver.fix_sys_path()
  suite = unittest.loader.TestLoader().discover(test_path)
  if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
    sys.exit(-1)

if __name__ == '__main__':
  SDK_PATH = SDK_PATH_manual
  TEST_PATH = TEST_PATH_manual
  if len(sys.argv)==2:
    SDK_PATH = sys.argv[1]
  main(SDK_PATH, TEST_PATH)
