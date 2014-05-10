#!/usr/bin/python
import sys
# Install the Python unittest2 package before you run this script.
import unittest

USAGE = """%prog SDK_PATH TEST_PATH
Run unit tests for App Engine apps."""

SDK_PATH_manual = '/usr/local/google_appengine'
TEST_PATH_manual = 'unittests'


def main(sdk_path, test_path):
  sys.path.insert(0, sdk_path)
  import dev_appserver
  dev_appserver.fix_sys_path()
  suite = unittest.loader.TestLoader().discover(test_path)
  unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
  print('UNITTESTS FOR MAYONE APPENGINE')
  SDK_PATH = SDK_PATH_manual
  TEST_PATH = TEST_PATH_manual
  SDK_PATH_override = raw_input('Enter SDK_PATH Override (Leave blank to use the default): ')
  if SDK_PATH_override:
      SDK_PATH = SDK_PATH_override
  print('STARTING UNITTESTS...')
  main(SDK_PATH, TEST_PATH)