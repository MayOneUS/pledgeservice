"""General utilities."""

import urlparse

def ConstantTimeIsEqual(a, b):
  """Securely compare two strings without leaking timing information."""
  if len(a) != len(b):
    return False
  acc = 0
  for x, y in zip(a, b):
    acc |= ord(x) ^ ord(y)
  return acc == 0


# TODO(hjfreyer): Pull into some kind of middleware?
def EnableCors(handler):
  """Inside a request, set the headers to allow being called cross-domain."""
  if 'Origin' in handler.request.headers:
    origin = handler.request.headers['Origin']
    _, netloc, _, _, _, _ = urlparse.urlparse(origin)
    if not (netloc == 'mayone.us' or netloc.endswith('.mayone.us')):
      logging.warning('Invalid origin: ' + origin)
      handler.error(403)
      return

    handler.response.headers.add_header('Access-Control-Allow-Origin', origin)
    handler.response.headers.add_header('Access-Control-Allow-Methods',
                                        'GET, POST')
    handler.response.headers.add_header('Access-Control-Allow-Headers',
                                        'content-type, origin')
