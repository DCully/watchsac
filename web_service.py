import logging

import cherrypy

from database.model import Model, Alert

logging.basicConfig(filename='web_service.log', level=logging.DEBUG)

from utils import utils
from utils import properties
import spellchecking
import forecasting
import sms
import session_token_manager

"""
API spec

Base URL:  https://watchsac.com

confirm phone number
URL: 			    https://watchsac.com/accounts
Method: 			PUT
Request body:  	    {"pn": "?", "conf_key": "?"}
Returns:			200 if OK, 400 if conf key doesnt match

create account with a new account key
URL: 			    https://watchsac.com/accounts
Method: 			POST
Request body:  	    {"u": "?", "p": "?", "pn": "?"}
Returns:			200 if OK, 400 is username/password is bad

get all current alerts
URL:      			https://watchsac.com/alerts
Header: 			Http basic auth username and password
Method: 			GET
Returns:			200 and JSON alerts list if OK, 401 if unauthorized, 404 otherwise

save a new alert or update an existing alert (update if ID field is present, new otherwise)
URL:      			https://watchsac.com/alerts
Header: 			Http basic auth username and password
Method: 			POST
Request body:	    {"id": 5, "name": "my alert name", "search_terms": ["patagonia", "sweater", "wool"]}
Returns:			200 if OK, 401 if unauthorized, 404 otherwise

delete an existing alert
URL:      			https://watchsac.com/alerts?id=<?>
Header: 			Http basic auth username and password
Method: 			DELETE
Returns:			204 No Content on success, 401 on unauthorized, 404 otherwise

spellcheck some search terms
URL:      			https://watchsac.com/spellcheck
Header: 			Http basic auth username and password
Method: 			POST
Returns:			200 on success with a JSON list of strings (with spelling corrected, in the same order) - 40x otherwise

get recent historical frequency for some search terms
URL:      			https://watchsac.com/forecast
Header: 			Http basic auth username and password
Method: 			POST
Returns:			200 on success with a JSON object mapping search terms to counts on success - 40x otherwise

"""


class App(object):
    pass


@cherrypy.expose  # /accounts
class AccountService(object):
    """ Simple API for creating a new User. """

    def __init__(self, model):
        self.model = model
        self.sms_client = sms.TwilioSMSClient()

    @staticmethod
    def __has_valid_json_data(req_json, expected_params=("u", "p", "pn")):
        # expecting:
        # {"u": "less-than-40-chars", "less-than-40-chars": "?", "pn": "+1234567890"}
        for expected_param in expected_params:
            if expected_param not in req_json:
                return False
        return True

    def __is_valid(self, req_json):
        if AccountService.__has_valid_json_data(req_json) is False:
            logging.info("Account setup request had bad json data")
            return False
        elif utils.is_valid_phone_number(req_json["pn"]) is False:
            logging.info("Account setup request had bad phone number")
            return False
        elif utils.is_valid_username(req_json["u"]) is False:
            logging.info("Account setup request had bad username")
            return False
        elif utils.is_valid_password(req_json["p"]) is False:
            logging.info("Account setup request had bad password")
            return False
        else:
            return True

    def __is_unique_username_and_number_combo(self, username, phone_number):
        current_users = self.model.load_users()
        for user in current_users:
            existing_username = user.user_name
            existing_phone_number = user.phone_number
            if username == existing_username and phone_number == existing_phone_number:
                return False
        return True

    def __is_authorized(self, req_json):
        username = req_json["u"]
        phone_number = req_json["pn"]
        if self.__is_unique_username_and_number_combo(username, phone_number):
            return True
        return False

    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        """
        Load the valid keys from the DB, and if the key is legit and the username/number
        combo doesn't already exist, save a new row into the users table.

        NOTE: There's a potential race condition here, if a person tries to submit many requests to create an
        account for the same username/phone number combo simultaneously. That is OK - MySQL will maintain consistency,
        and we will avoid having it happen in the UI with some basic client-side rate limiting (to stop dup-clicking).

        Alternatively, we could lock the table at the start of this new-user-signup process...
        but that seems excessive in this case.
        """
        logging.info("Received new account setup request")
        data = cherrypy.request.json
        if not self.__is_valid(data):
            logging.info("Invalid account setup request: %s" % str(data))
            cherrypy.response.status = 400
        elif not self.__is_authorized(data):
            logging.info("Unauthorized account setup request: %s" % str(data))
            cherrypy.response.status = 401
        elif self.__save_new_account(data["u"], data["p"], data["pn"]) is not None:
            logging.info("Successful account setup request for user: %s" % str(data["u"]))
            cherrypy.response.status = 200
            return {}
        else:
            logging.info("Something went wrong with an account setup request: %s" % str(data))
            cherrypy.response.status = 400  # collision in the DB - assume it was a dup record

    def __is_valid_conf_pair(self, pn, conf_key):
        """ load conf keys from DB and make sure this pn-conf_key pair is in there """
        for pair in self.model.load_activation_key_pairs():
            phone_number = pair.phone_number
            activation_key = pair.activation_key
            logging.debug("%s - %s" % (phone_number, activation_key))
            if str(pn) == str(phone_number) and str(activation_key) == str(conf_key):
                return True
        return False

    def __send_activation_text_msg(self, phone_number, activation_key):
        if properties.USE_SMS_ACCOUNT_SETUP_VALIDATION:
            logging.info("Sending text message to %s with key %s" % (phone_number, activation_key))
            return self.sms_client.send_activation_key(phone_number, activation_key)
        else:
            return True

    def __activate_account(self, u, pn):
        self.model.activate_user(u, pn)

    def __save_new_account(self, username, password, phone_number):
        """ Takes a sanitized username, password, and phone number, then saves a row for them in the users table.
        Returns a User object if successful - None otherwise. """
        activation_key = utils.generate_new_activation_key()
        self.model.save_activation_key_pair(phone_number, activation_key)
        if not self.__send_activation_text_msg(phone_number, activation_key):
            logging.error("An error occurred trying to send activation text message")
            cherrypy.response.status = 400
        else:
            return self.model.save_user(phone_number, username, utils.encrypt(password))

    @cherrypy.tools.accept(media='application/json')
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self):
        """ Try to an account record with the given username and phone number, and then check that the
        confirmation key matches the one we saved when they initially POSTed in to this endpoint. """
        logging.info("Received new account phone number confirmation request")
        data = cherrypy.request.json
        cherrypy.response.status = 400
        if self.__has_valid_json_data(data, expected_params=("u", "pn", "conf_key")) is False:
            logging.info("Bad JSON for account confirmation request: %s" % str(data))
        elif utils.is_valid_username(data["u"]) is False:
            logging.info("Bad username for account confirmation request - %s" % str(data))
        elif utils.is_valid_phone_number(data["pn"]) is False:
            logging.info("Bad phone number PUT to /accounts: %s" % str(data))
        elif not self.__is_valid_conf_pair(data["pn"], data["conf_key"]):
            logging.info("Bad conf key PUT to /accounts: %s" % str(data))
        else:
            logging.info("Successful account activation request PUT to /accounts: %s" % str(data))
            self.__activate_account(data["u"], data["pn"])
            cherrypy.response.status = 200
            return {}


@cherrypy.expose  # /alerts
class AlertService(object):
    """ API for CRUD operations on Alerts. """

    def __init__(self, model):
        self.model = model
        self.token_mgr = session_token_manager.TokenManager()

    def __check_token(self, cherrypy_request):
        # use token_mgr to see if they've got a good token
        u = None
        p = None
        try:
            if "watchsac" in cherrypy_request.cookie:
                token = cherrypy_request.cookie["watchsac"].value
                u, p = self.token_mgr.is_token_good(token)
        except Exception as e:
            logging.exception(e)
        finally:
            return u, p

    def __set_token(self, username, password, cherrypy_response):
        # use the utils module to generate a token, set it in a cookie, and save it in memory in self.token_mgr
        token = utils.generate_new_session_cookie_token()
        self.token_mgr.set_token_for_user(token, username, password)
        cherrypy_response.cookie["watchsac"] = token
        cherrypy_response.cookie["watchsac"]['max-age'] = 3600

    def validate_password(self, realm, username, password_attempt):
        """
        Cherrypy calls into here automatically before entering the handlers (see config below).
        This is on the AlertService object so that we can get easy access to the model.
        """

        logging.debug("Checking cookie token first...")
        token_user_name, token_pwd = self.__check_token(cherrypy.request)
        if token_user_name is not None:
            logging.debug("Cookie token worked, user is %s, skipping u-p check" % token_user_name)
            return True
        logging.debug("About to validate u-p - fetching users...")
        users = self.model.load_users()
        logging.debug("Validating u-p: found %d users" % len(users))
        logging.debug("User-submitted name is %s" % username)
        for user in users:
            logging.debug("Checking if user %s is %s" % (username, user.user_name))
            if str(user.user_name) == str(username):
                if utils.verify(password_attempt, user.password):
                    logging.info("User %s verified" % username)
                    self.__set_token(username, password_attempt, cherrypy.response)
                    return True
        return False

    def __get_user_by_name(self, username):
        logging.debug("getting user by name %s..." % username)
        users = self.model.load_users()
        logging.debug("loaded %d users" % len(users))
        for user in users:
            logging.debug("user name is %s" % user.user_name)
            if user.user_name == username:
                return user

    def __get_alerts_for_user(self, user_id):
        logging.debug("getting alerts for user with id: %s" % user_id)
        alerts = self.model.load_all_active_alerts_with_phone_numbers()
        results = []
        for alert in alerts:
            if int(alert.user_id) == int(user_id):
                results.append(alert)
        return results

    def __get_user_name(self, cherrypy_request):
        u = None
        try:
            token = cherrypy_request.cookie["watchsac"].value
            u = self.token_mgr.get_user_for_token(token)
            if u is not None:
                return u
        except:
            pass
        try:
            u = cherrypy_request.login
            if u is not None:
                return u
        except:
            pass
        return None

    @cherrypy.tools.json_out()
    def GET(self):
        user_id = self.__get_user_by_name(self.__get_user_name(cherrypy.request))._id
        return [x.to_dict() for x in self.__get_alerts_for_user(user_id)]

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        user = self.__get_user_by_name(self.__get_user_name(cherrypy.request))
        alerts = self.__get_alerts_for_user(user._id)
        data = cherrypy.request.json
        try:
            new_alert = Alert.build_alert_from_json_and_user(data, user)
        except Exception as e:
            cherrypy.response.status = 400
            return  # malformed alert - return 400 immediately
        logging.debug("received new alert: %s" % str(new_alert.to_dict()))
        if new_alert.alert_id is not None:
            cherrypy.response.status = 400  # might get this back if they pass someone else's alert_id
            for existing_alert in alerts:
                logging.debug("Comparing to this existing alert: %s" % str(existing_alert.to_dict()))
                if int(existing_alert.alert_id) == int(new_alert.alert_id):
                    self.model.update_alert(new_alert)
                    cherrypy.response.status = 200
                    return {}
        else:
            self.model.save_alert(new_alert)

    @cherrypy.tools.json_out()
    def DELETE(self, id):
        alert_id = int(id)
        user = self.__get_user_by_name(self.__get_user_name(cherrypy.request))
        alerts = self.__get_alerts_for_user(user._id)
        cherrypy.response.status = 400
        for alert in alerts:
            if int(alert.alert_id) == alert_id:
                self.model.archive_alert(alert)
                cherrypy.response.status = 200
                return {}


@cherrypy.expose  # /spellcheck
class SpellcheckingService(object):

    def __init__(self):
        # build the internal spellchecking service
        # this automatically loads our bloom filter from the configured location on disk
        # the service will also handle re-loading on an hourly basis
        self.service = spellchecking.SpellcheckingService()

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        logging.info("received POST For spellchecking service")
        data = cherrypy.request.json
        try:
            search_terms_list = [x for x in data]
            recommendations = []
            logging.info("Received spellchecking request for terms: %s" % str(search_terms_list))
            for st in search_terms_list:
                recommended_alt = self.service.try_to_correct(st)
                if recommended_alt is None:
                    recommended_alt = st  # same string as input, if we couldn't make an improvement
                recommendations.append(recommended_alt)
            return recommendations
        except Exception as e:
            logging.exception(e)
            cherrypy.response.status = 400
            return  # malformed request - return 400


@cherrypy.expose  # /forecast
class ForecastingService(object):

    def __init__(self):
        self.service = forecasting.ForecastingService()

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        logging.info("received POST to forecasting service")
        data = cherrypy.request.json
        try:
            search_terms_list = [x for x in data]
            counts = {}
            logging.info("Received spellchecking request for terms: %s" % str(search_terms_list))
            for st in search_terms_list:
                counts[st] = self.service.get_count_for(st)
            counts["(all of them combined)"] = self.service.get_count_for_all(search_terms_list)
            return counts
        except Exception as e:
            logging.exception(e)
            cherrypy.response.status = 400
            return  # malformed request - return 400


def start_webapp(premade_db_conn_pool=None):

    model = Model(conn_pool_size=5, premade_db_conn_pool=premade_db_conn_pool)

    account_service = AccountService(model)
    alert_service = AlertService(model)
    static_app_service = App()
    spellchecking_service = SpellcheckingService()
    forecasting_service = ForecastingService()

    cherrypy.tree.mount(static_app_service, "/", {
        '/':
        {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': properties.CLIENT_APP_DIR,
            'tools.staticdir.index': 'index.html',
        }
    })
    cherrypy.tree.mount(account_service, '/accounts', {
        '/':
        {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.json_in.force': False
        }
    })
    cherrypy.tree.mount(alert_service, '/alerts', {
        '/':
        {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.auth_basic.on': True,
            'tools.auth_basic.realm': 'localhost',
            'tools.auth_basic.checkpassword': alert_service.validate_password,
            'tools.json_in.force': False
        }
    })
    cherrypy.tree.mount(spellchecking_service, "/spellcheck", {
        '/':
            {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                'tools.auth_basic.on': True,
                'tools.auth_basic.realm': 'localhost',
                'tools.auth_basic.checkpassword': alert_service.validate_password,
                'tools.json_in.force': False
            }
    })
    cherrypy.tree.mount(forecasting_service, "/forecast", {
        '/':
            {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                'tools.auth_basic.on': True,
                'tools.auth_basic.realm': 'localhost',
                'tools.auth_basic.checkpassword': alert_service.validate_password,
                'tools.json_in.force': False
            }
    })
    cherrypy.server.socket_host = '0.0.0.0'
    cherrypy.server.socket_port = 8080
    cherrypy.engine.start()


def block():
    cherrypy.engine.block()


def stop():
    cherrypy.engine.stop()


if __name__ == "__main__":
    start_webapp()
    block()
