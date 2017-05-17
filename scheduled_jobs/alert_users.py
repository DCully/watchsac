import logging

from fuzzywuzzy import fuzz

import sms
from database.model import Model

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


def send_and_record_alerts(alerts_to_send, current_steal, model):
    """ Sends out text messages and records each one sent out in the DB. """
    sms_client = sms.TwilioSMSClient()
    for alert in alerts_to_send:
        if sms_client.send_alert(alert):
            model.save_sent_alert(alert, current_steal.deal_id)


def filter_alerts_by_phone_number_cap(alerts_to_send, sent_counts_by_user_id):
    filtered_alerts_to_send = []
    for alert in alerts_to_send:
        if alert.user_id in sent_counts_by_user_id:
            if sent_counts_by_user_id[alert.user_id] < 3:
                filtered_alerts_to_send.append(alert)
                sent_counts_by_user_id[alert.user_id] += 1
    return filtered_alerts_to_send


def main():
    """ Exit 0 on success, 1 on failure. """
    exit_code = 0
    try:
        model = Model()
        all_active_alerts = model.load_all_active_alerts_with_phone_numbers()
        current_steal = model.load_current_steal()
        sent_alerts_counts = model.load_sent_alerts_count_by_user_id()
        if current_steal is not None:
            previously_sent_alert_ids = model.load_sent_alerts_by_deal_id(current_steal.deal_id)
            alerts_to_send = filter_alerts_by_previously_sent(all_active_alerts, previously_sent_alert_ids)
            alerts_to_send = filter_alerts_by_current_steal_is_relevant(alerts_to_send, current_steal)
            alerts_to_send = filter_alerts_by_phone_number_cap(alerts_to_send, sent_alerts_counts)
            send_and_record_alerts(alerts_to_send, current_steal, model)
    except Exception as e:
        logging.error(e)
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    exit(main())
