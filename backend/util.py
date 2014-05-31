"""General utilities."""

def ConstantTimeIsEqual(a, b):
  """Securely compare two strings without leaking timing information."""
  if len(a) != len(b):
    return False
  acc = 0
  for x, y in zip(a, b):
    acc |= ord(x) ^ ord(y)
  return acc == 0

def SplitName(name_to_split):
  # Split apart the name into first and last. Yes, this sucks, but adding the
  # name fields makes the form look way more daunting. We may reconsider this.
  name_parts = name_to_split.split(None, 1)
  first_name = name_parts[0]
  if len(name_parts) == 1:
    last_name = ''
    logging.warning('Could not determine last name: %s', data['name'])
  else:
    last_name = name_parts[1]
  
  return (first_name, last_name)