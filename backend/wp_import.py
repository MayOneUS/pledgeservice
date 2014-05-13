import os
import json
import logging
import webapp2
import datetime

from google.appengine.api import mail
from google.appengine.ext import db

import model

# NOTE(hjfreyer): Commenting this out for now, as it's hopefully
# obsolete, and I want to get rid of config_NOCOMMIT. If this is
# necessary again, we can either hard-code the constant here and not
# check it in, or incorporate this key into the Secrets model. Or put
# it behind an admin handler.
#
# import config_NOCOMMIT


# def constantTimeIsEqual(a, b):
#   if len(a) != len(b):
#     return False
#   acc = 0
#   for x, y in zip(a, b):
#     acc |= ord(x) ^ ord(y)
#   return acc == 0


# class ImportHandler(webapp2.RequestHandler):
#   def post(self):
#     if not constantTimeIsEqual(
#         self.request.get("import_key"), config_NOCOMMIT.IMPORT_SECRET_KEY):
#       self.error(400)
#       self.response.write('Invalid request')
#       return

#     try:
#       data = json.loads(self.request.body)
#     except:
#       logging.warning("Bad JSON request")
#       self.error(400)
#       self.response.write('Invalid request')
#       return

#     # validate required and non-string fields
#     for key in ('wp_post_id', 'email', 'stripe_customer_id', 'amount',
#         'timestamp'):
#       if key not in data:
#         self.error(400)
#         self.response.write("Invalid request")
#         return

#     try:
#       wp_post_id = int(data["wp_post_id"])
#       amount = int(data["amount"])
#       timestamp = int(data["timestamp"])
#     except ValueError:
#       self.error(400)
#       self.response.write("Invalid request")
#       return

#     email = data["email"]
#     if not mail.is_email_valid(email):
#       self.error(400)
#       self.response.write("Invalid request: bad email address")
#       return

#     stripe_customer_id = data['stripe_customer_id']

#     model.User.createOrUpdate(
#             email=email,
#             occupation=(data.get("occupation", None) or None),
#             employer=(data.get("employer", None) or None),
#             phone=(data.get("phone", None) or None),
#             target=(data.get("target", None) or None),
#             from_import=True)

#     @db.transactional
#     def txn():
#       pledge = model.WpPledge.get_by_key_name(str(wp_post_id))
#       if pledge is None:
#         pledge = model.WpPledge(key_name=str(wp_post_id),
#                                 wp_post_id=wp_post_id,
#                                 email=email,
#                                 stripeCustomer=stripe_customer_id,
#                                 amountCents=amount,
#                                 donationTime=datetime.datetime.fromtimestamp(
#                                     timestamp),
#                                 url_nonce=os.urandom(32).encode("hex"))
#       else:
#         pledge.email = email
#         pledge.stripeCustomer = stripe_customer_id
#         pledge.amountCents = amount
#         pledge.donationTime = datetime.datetime.fromtimestamp(timestamp)

#       def setField(name, value):
#         if value:
#           setattr(pledge, name, value)

#       setField("occupation", data.get("occupation"))
#       setField("employer", data.get("employer"))
#       setField("phone", data.get("phone"))
#       setField("target", data.get("target"))

#       pledge.put()

#     txn()
