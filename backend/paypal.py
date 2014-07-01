"""Helpers for retriving data from Paypal."""

import logging
import model
import urlparse
import urllib
import pprint
import copy

from google.appengine.api import urlfetch
def send_request(fields):
    config = model.Config.get()

    fields["VERSION"] = "113"
    fields["USER"] =  config.paypal_user
    fields["PWD"] =  config.paypal_password
    fields["SIGNATURE"] = config.paypal_signature

    form_data = urllib.urlencode(fields)

    result = urlfetch.fetch(url=config.paypal_api_url, payload=form_data, method=urlfetch.POST,
                headers={'Content-Type': 'application/x-www-form-urlencoded'})
    result_map = urlparse.parse_qs(result.content)

    if 'ACK' in result_map:
        if result_map['ACK'][0] == "Success":
            return (True, result_map)
   
        logging.warning("Paypal returned an error:")
        logging.warning(pprint.pformat(result_map))
        return (False, result_map)

    logging.warning("Could not contact Paypal:")
    logging.warning(result.content)
    return False, result.content

def encode_data(data):
    d = copy.copy(data)

    # Trim out a few items we don't need to transmit
    del d['amountCents']
    del d['name']
    del d['payment']

    return urllib.urlencode(d)

def SetExpressCheckout(host_url, data):

    amount = data['amountCents'] / 100

    encoded_data = encode_data(data)

    # Paypal limits our custom field to 200 characters
    #  If there isn't room for the team, let's strip it out,
    #  and try to pick it up via cookie later
    if len(encoded_data) >= 200:      
        del data['team']
        encoded_data = encode_data(data)

    if len(encoded_data) >= 200:
        logging.warning("Encoded data length %d too long" % len(encoded_data))
        logging.info("Data was: %s" % encoded_data)
        return False, ""


    form_fields = {
      "METHOD": "SetExpressCheckout",
      "RETURNURL": host_url + '/r/paypal_return',
      "CANCELURL": host_url + '/pledge',
      "EMAIL": data['email'],
      "PAYMENTREQUEST_0_PAYMENTACTION": "Sale",
      "PAYMENTREQUEST_0_DESC": "Non-refundable donation to Mayday PAC",
      "PAYMENTREQUEST_0_AMT":  "%d.00" % amount,
      "PAYMENTREQUEST_0_ITEMAMT":  "%d.00" % amount,
      "PAYMENTREQUEST_0_CUSTOM": encoded_data,
      "L_PAYMENTREQUEST_0_NAME0": "Non-refundable donation to Mayday PAC",
      "L_PAYMENTREQUEST_0_AMT0":  "%d.00" % amount,
      "ALLOWNOTE":  "0",
      "SOLUTIONTYPE":  "Sole",
      "BRANDNAME":  "MayDay PAC",
      # TODO FIXME - LOGOIMG trumps if given; it's a different look with HDRIMG
      "LOGOIMG":  host_url + '/static/paypal_logoimg.png',
      #"HDRIMG":   self.request.host_url + '/static/paypal_hdrimg.png',
      #"PAYFLOWCOLOR":    "00FF00",
      #"CARTBORDERCOLOR": "0000FF",
      # TODO FIXME Explore colors.  Seems like either color has same result, and cart trumps
    }

    rc, results = send_request(form_fields)
    if rc:
        config = model.Config.get()
        return rc, config.paypal_url + "?cmd=_express-checkout&token=" + results['TOKEN'][0]

    return False, ""

def DoExpressCheckoutPayment(token, payer_id, amount, custom):

    form_fields = {
      "METHOD": "DoExpressCheckoutPayment",
      "TOKEN": token,
      "PAYERID": payer_id,
      "PAYMENTREQUEST_0_PAYMENTACTION": "Sale",
      "PAYMENTREQUEST_0_DESC": "Non-refundable donation to Mayday PAC",
      "PAYMENTREQUEST_0_AMT":  amount,
      "PAYMENTREQUEST_0_ITEMAMT":  amount,
      "PAYMENTREQUEST_0_CUSTOM": custom,
    }

    rc, results = send_request(form_fields)

    return rc, results

