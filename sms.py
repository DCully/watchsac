import logging

from twilio.rest import Client

from utils import properties


class TwilioSMSClient(object):

    def __init__(self):
        pass

    def send_alert(self, alert):
        """ Send a text message to alert the user about the current steal using the Twilio API. """
        try:
            client = Client(properties.TWILIO_ACCOUNT_SID, properties.TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                to=alert.phone_number,
                from_=properties.TWILIO_PHONE_NUMBER,
                body="Look at steepandcheap.com for " + alert.alert_name
            )
            logging.info("Alert text msg sent to " + alert.phone_number + ", twilio sid: " + message.sid)
            return True
        except Exception as e:

            logging.error("An error occurred sending an alert:")
            logging.error(e)
            return False

    def send_activation_key(self, pn, conf_key):
        try:
            client = Client(properties.TWILIO_ACCOUNT_SID, properties.TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                to=pn,
                from_=properties.TWILIO_PHONE_NUMBER,
                body="Activation key: " + conf_key
            )
            logging.info("Account activation text msg sent to " + pn + ", twilio sid: " + message.sid)
            return True
        except Exception as e:
            logging.error("An error occurred sending an activation text msg:")
            logging.error(e)
            return False
