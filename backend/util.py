"""General utilities."""

def ConstantTimeIsEqual(a, b):
  """Securely compare two strings without leaking timing information."""
  if len(a) != len(b):
    return False
  acc = 0
  for x, y in zip(a, b):
    acc |= ord(x) ^ ord(y)
  return acc == 0
  