import mysql
import logging


class Alert(object):
    """
    Data object for alert rows (phone number for user added for convenience). JSON like:
    {"search_terms": ["liberty ridge", "waterproof", "leather"], "name": "hello world", "id": 1}
    """

    def __init__(self, user_id, alert_id, alert_name, search_terms, phone_number):
        self.user_id = user_id
        self.alert_id = alert_id
        self.alert_name = alert_name
        self.search_terms = search_terms
        if type(self.search_terms) == str:
            self.search_terms = search_terms.split("|")
        self.phone_number = phone_number

    @staticmethod
    def build_alert_from_json_and_user(json_obj, user):
        user_id = user._id
        alert_id = None
        if "id" in json_obj:
            alert_id = json_obj["id"]
        alert_name = json_obj["name"]
        search_terms = [x for x in json_obj["search_terms"]]
        search_terms = [x.replace("|", "") for x in search_terms]
        if len("".join(search_terms)) > 1000:
            raise Exception("Search terms too long!")
        phone_number = user.phone_number
        return Alert(user_id, alert_id, alert_name, search_terms, phone_number)

    def get_db_search_terms(self):
        # prep search terms for DB storage (fix this hack, search terms should have their own table)
        search_terms = ""
        for search_term in self.search_terms[:-1]:
            search_terms = search_terms + search_term + "|"
        search_terms += self.search_terms[-1]
        return search_terms

    def to_dict(self):
        data = dict()
        data["name"] = self.alert_name
        data["id"] = self.alert_id
        data["search_terms"] = self.search_terms
        return data


class CurrentSteal(object):
    """ Data object for current steal rows. """
    def __init__(self, deal_id, product_name, product_description):
        self.deal_id = deal_id
        self.product_name = product_name
        self.product_description = product_description


class User(object):
    """ Data object for user rows. """
    def __init__(self, _id, phone_number, user_name, password):
        self._id = _id
        self.phone_number = phone_number
        self.user_name = user_name
        self.password = password


class NewAccountKey(object):
    """ Data object for user rows. """
    def __init__(self, _id, key):
        self._id = _id
        self.key = key


class Model(object):
    """ DAO for our MySQL DB. """

    def __init__(self, conn_pool_size=1, premade_db_conn_pool=None):
        if premade_db_conn_pool is not None:
            # this just makes it easy to mock out the back end (behind our model object) for testing
            self.conn_pool = premade_db_conn_pool
        else:
            self.conn_pool = mysql.DBConnPool(conn_count=conn_pool_size)

    def __del__(self):
        self.conn_pool.close_all()

    #
    # read new account keys
    #

    def load_new_account_keys(self):
        """ Returns a list of NewAccountKey objects (only loads rows where active = 1). """
        logging.info("Loading new account creation keys...")
        sql = "select new_account_keys.id, new_account_keys.new_account_key " \
              "from new_account_keys " \
              "where new_account_keys.active = 1"
        results = []
        db_conn = None
        try:
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(sql)
            rs = cursor.fetchall()
            for _id, key in rs:
                results.append(NewAccountKey(_id, key))
        except Exception as e:
            logging.error("An exception occurred loading new account keys from the database:")
            logging.error(e)
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)
        return results

    #
    # read/write users
    #

    def load_users(self):
        """ Returns a list of Users. """
        logging.info("Loading users in model...")
        sql = "select users.id, users.phone_number, users.username, users.password from users"
        results = []
        db_conn = None
        try:
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(sql)
            rs = cursor.fetchall()
            logging.debug("raw load users result set: %s" % str(rs))
            for _id, phone_number, user_name, password in rs:
                results.append(User(_id, phone_number, user_name, password))
        except Exception as e:
            logging.exception("An exception occurred loading users from the database:")
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)
        logging.info("Loaded %d users" % len(results))
        return results

    def save_user(self, phone_number, user_name, password):
        """ Returns a User object representing the new record, or None if the save failed.
        NOTE: Password should already be encrypted before it gets passed in here! """
        logging.info("Saving new user...")
        save_sql = "insert into users (phone_number, username, password) values (%s, %s, %s)"
        load_sql = "select id from users where username=%s"
        db_conn = None
        result = None
        try:
            logging.info("save the record first...")
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(save_sql, (phone_number, user_name, password))
            db_conn.commit()
            logging.info("now load it back...")
            cursor.execute(load_sql, user_name)
            rs = cursor.fetchall()
            new_id = rs[0][0]
            # build a representative User instance to be returned
            result = User(new_id, phone_number, user_name, password)
        except Exception as e:
            logging.exception("An exception occurred saving a new user to the database:")
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)
        return result

    #
    # read/write alerts
    #

    def save_alert(self, alert):
        """ Saves a new alert and returns None. """
        logging.info("Saving new alert...")
        save_sql = "insert into alerts (user_id, alert_name, search_terms) values (%s, %s, %s)"
        db_conn = None
        try:
            # save the new record
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(save_sql, (alert.user_id, alert.alert_name, alert.get_db_search_terms()))
            db_conn.commit()
        except Exception as e:
            logging.exception("An exception occurred saving a new alert:")
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)

    def update_alert(self, alert):
        """ Updates the alert row with the matching ID. """
        logging.info("Updating alert...")
        save_sql = "update alerts " \
                   "set " \
                   "alerts.user_id = %s, " \
                   "alerts.alert_name = %s, " \
                   "alerts.search_terms = %s " \
                   "where alerts.id = %s"
        db_conn = None
        try:
            # save the new record
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(save_sql, (alert.user_id, alert.alert_name, alert.get_db_search_terms(), alert.alert_id))
            db_conn.commit()
        except Exception as e:
            logging.exception("An exception occurred updating an alert:")
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)

    def archive_alert(self, alert):
        logging.info("Archiving alert with ID %d" % int(alert.alert_id))
        archive_sql = "update alerts set alerts.active = 0 where alerts.id = %s"
        db_conn = None
        try:
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(archive_sql, (alert.alert_id,))
            db_conn.commit()
        except Exception as e:
            logging.exception("An exception occurred archiving an alert:")
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)

    def load_all_active_alerts_with_phone_numbers(self):
        """ Returns a list of Alert instances (or an empty list).  """
        logging.info("Loading active alerts...")
        sql = "select alerts.id, alerts.user_id, alerts.alert_name, alerts.search_terms, users.phone_number " \
              "from alerts " \
              "join users " \
              "on users.id = alerts.user_id " \
              "where alerts.active = 1"
        results = []
        db_conn = None
        try:
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(sql)
            rs = cursor.fetchall()
            for alert_id, user_id, alert_name, search_terms, phone_number in rs:
                results.append(Alert(user_id, alert_id, alert_name, search_terms, phone_number))
        except Exception as e:
            logging.exception("An exception occurred loading active alerts from the database:")
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)
        return results

    #
    # read/write current steal records
    #

    def save_current_steal(self, title, product_description):
        logging.info("Saving title and product desc:  %s - %s" % (title, product_description))
        db_conn = None
        try:
            # trim for max table sizes
            title = title[:254]
            product_description = product_description[:4094]
            db_conn = self.conn_pool.get_conn()
            with db_conn.cursor() as cursor:
                sql = "insert ignore into deals (product_name, product_description) values (%s, %s)"
                cursor.execute(
                    sql,
                    (title, product_description)
                )
                db_conn.commit()
            logging.info("Save success for title: %s" % (title,))
        except Exception as e:
            logging.error("An exception occurred saving the title and product description: ")
            logging.error(e)
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)

    def load_current_steal(self):
        """ Returns a CurrentSteal instance, or None. """
        logging.info("Loading current steal...")
        sql = "select deals.id, deals.product_name, deals.product_description " \
              "from deals " \
              "order by deals.created desc limit 1 "
        result = None
        db_conn = None
        try:
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(sql)
            r = cursor.fetchall()[0]
            result = CurrentSteal(r[0], r[1], r[2])
        except Exception as e:
            logging.error("An exception occurred loading current steal from the database:")
            logging.error(e)
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)
        return result

    #
    # read/write sent alert records
    #

    def load_sent_alerts_by_deal_id(self, deal_id):
        """ Returns a list of alert IDs.  """
        logging.info("Loading previously sent alerts for current deal...")
        sql = "select sent_alerts.alert_id from sent_alerts where sent_alerts.deal_id = %s "
        results = []
        db_conn = None
        try:
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            cursor.execute(sql, (deal_id,))
            rs = cursor.fetchall()
            for alert_id in rs:
                results.append(alert_id[0])
        except Exception as e:
            logging.error("An error occurred loading previously sent alerts:")
            logging.error(e)
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)
        return results

    def save_sent_alert(self, alert, deal_id):
        """ Write down in the DB that we sent out this alert. """
        logging.info("Saving sent alert, alert id: %d, deal id: %d" % (alert.alert_id, deal_id))
        db_conn = None
        try:
            db_conn = self.conn_pool.get_conn()
            cursor = db_conn.cursor()
            sql = "insert into sent_alerts (deal_id, alert_id) values (%s, %s)"
            cursor.execute(sql, (deal_id, alert.alert_id))
            db_conn.commit()
        except Exception as e:
            logging.error("An exception occurred saving a sent alert record:")
            logging.error(e)
        finally:
            if db_conn is not None:
                self.conn_pool.return_conn(db_conn)
