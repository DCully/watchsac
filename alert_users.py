import logging
from fuzzywuzzy import fuzz
from twilio.rest import Client
import properties
from model import Model

"""
This process loads active alerts, determines whether these alerts
match the latest current steal in our DB, and sends messages as necessary.
"""

logging.basicConfig(filename='alert_users.log', level=logging.DEBUG)


def filter_alerts_by_previously_sent(all_active_alerts, previously_sent_alert_ids):
    """ Returns a list of Alerts.  """
    logging.info("Filtering alerts by previously sent...")
    logging.info("All active alerts: %s" % str(all_active_alerts))
    logging.info("Previously sent alerts: %s" % str(previously_sent_alert_ids))
    filtered_alerts = []
    for alert in all_active_alerts:
        alert_id = alert.alert_id
        if alert_id not in previously_sent_alert_ids:
            filtered_alerts.append(alert)
    logging.info("Returning %d alerts after filtering by previously sent" % len(filtered_alerts))
    return filtered_alerts


def filter_alerts_by_current_steal_is_relevant(all_active_alerts, current_steal):
    """ Returns a list of Alerts. """
    logging.info("Filtering alerts by relevance...")
    logging.info("All active alerts: %s" % str(all_active_alerts))
    logging.info("Current steal deal ID: %s" % str(current_steal.deal_id))
    filtered_alerts = []
    for alert in all_active_alerts:
        search_term_desc_scores = [fuzz.token_set_ratio(search_term, current_steal.product_description) for search_term in alert.search_terms]
        avg_search_term__desc_score = float(sum(search_term_desc_scores)) / float(len(search_term_desc_scores))
        top_search_term_title_score = float(max([fuzz.token_set_ratio(search_term, current_steal.product_name) for search_term in alert.search_terms]))
        if avg_search_term__desc_score > 90.0 and top_search_term_title_score > 90.0:
            filtered_alerts.append(alert)
    return filtered_alerts


def send_alert(alert):
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


def send_and_record_alerts(alerts_to_send, current_steal, model):
    """ Sends out text messages and records each one sent out in the DB. """
    for alert in alerts_to_send:
        if send_alert(alert):
            model.save_sent_alert(alert, current_steal.deal_id)


def main():
    """ Exit 0 on success, 1 on failure. """
    exit_code = 0
    try:
        model = Model()
        all_active_alerts = model.load_all_active_alerts_with_phone_numbers()
        current_steal = model.load_current_steal()
        if current_steal is not None:
            previously_sent_alert_ids = model.load_sent_alerts_by_deal_id(current_steal.deal_id)
            alerts_to_send = filter_alerts_by_previously_sent(all_active_alerts, previously_sent_alert_ids)
            alerts_to_send = filter_alerts_by_current_steal_is_relevant(alerts_to_send, current_steal)
            send_and_record_alerts(alerts_to_send, current_steal, model)
    except Exception as e:
        logging.error(e)
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    exit(main())
