import cherrypy
from model import Model, Alert
import logging
import utils
import properties

"""
API spec - 4 RESTful HTTPS actions

Base URL:  https://watchsac.com

1) create account with a new account key
URL: 			    https://watchsac.com/accounts
Method: 			POST
Request body:  	    {"u": "?", "p": "?", "key": "?", "pn": "?"}
Returns:			200 if OK, 400 is username/password is bad, 401 if key was wrong

2) get all current alerts
URL:      			https://watchsac.com/alerts
Header: 			Http basic auth username and password
Method: 			GET
Returns:			200 and JSON alerts list if OK, 401 if unauthorized, 404 otherwise

3) save a new alert or update an existing alert (update if ID field is present, new otherwise)
URL:      			https://watchsac.com/alerts
Header: 			Http basic auth username and password
Method: 			POST
Request body:	    {"id": 5, "name": "my alert name", "search_terms": ["patagonia", "sweater", "wool"]}
Returns:			200 if OK, 401 if unauthorized, 404 otherwise

4) delete an existing alert
URL:      			https://watchsac.com/alerts?id=<?>
Header: 			Http basic auth username and password
Method: 			DELETE
Returns:			204 No Content on success, 401 on unauthorized, 404 otherwise
"""

logging.basicConfig(filename='web_service.log', level=logging.DEBUG)


class App(object):
    pass


@cherrypy.expose  # /accounts
class AccountService(object):
    """ Simple API for creating a new User. """

    def __init__(self, model):
        self.model = model

    @staticmethod
    def __has_valid_json_data(req_json):
        # expecting:
        # {"u": "less-than-40-chars", "less-than-40-chars": "?", "key": "(not checked here)", "pn": "+1234567890"}
        for expected_param in ["u", "p", "key", "pn"]:
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

    def __is_valid_key(self, key):
        valid_new_account_keys = self.model.load_new_account_keys()
        for vk in valid_new_account_keys:
            if str(key) == str(vk.key):
                return True
        return False

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
        key = req_json["key"]
        phone_number = req_json["pn"]
        if self.__is_valid_key(key) and self.__is_unique_username_and_number_combo(username, phone_number):
            return True
        return False

    def __save_new_account(self, username, password, phone_number):
        """ Takes a sanitized username, password, and phone number, then saves a row for them in the users table.
        Returns a User object if successful - None otherwise. """
        return self.model.save_user(phone_number, username, utils.encrypt(password))

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


@cherrypy.expose  # /alerts
class AlertService(object):
    """ API for CRUD operations on Alerts. """

    def __init__(self, model):
        self.model = model

    def validate_password(self, realm, username, password_attempt):
        """
        Cherrypy calls into here automatically before entering the handlers (see config below).
        This is on the AlertService object so that we can get easy access to the model.
        """
        logging.debug("About to validate u-p - fetching users...")
        users = self.model.load_users()
        logging.debug("Validating u-p: found %d users" % len(users))
        logging.debug("User-submitted name is %s" % username)
        for user in users:
            logging.debug("Checking if user %s is %s" % (username, user.user_name))
            if str(user.user_name) == str(username):
                if utils.verify(password_attempt, user.password):
                    logging.info("User %s verified" % username)
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

    @cherrypy.tools.json_out()
    def GET(self):
        user_id = self.__get_user_by_name(cherrypy.request.login)._id
        return [x.to_dict() for x in self.__get_alerts_for_user(user_id)]

    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        user = self.__get_user_by_name(cherrypy.request.login)
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
        user = self.__get_user_by_name(cherrypy.request.login)
        alerts = self.__get_alerts_for_user(user._id)
        cherrypy.response.status = 400
        for alert in alerts:
            if int(alert.alert_id) == alert_id:
                self.model.archive_alert(alert)
                cherrypy.response.status = 200
                return {}


def start_webapp(premade_db_conn_pool=None):

    model = Model(conn_pool_size=5, premade_db_conn_pool=premade_db_conn_pool)

    account_service = AccountService(model)
    alert_service = AlertService(model)
    static_app_service = App()

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
