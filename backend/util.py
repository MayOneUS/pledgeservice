"""Utility methods for mayone.us."""

def ConstantTimeIsEqual(a, b):
  if len(a) != len(b):
    return False
  acc = 0
  for x, y in zip(a, b):
    acc |= ord(x) ^ ord(y)
  return acc == 0
