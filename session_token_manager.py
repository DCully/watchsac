import threading
from datetime import datetime, timedelta
import logging


class TokenManager(object):

    def __init__(self):
        self.__tokens_to_users_and_timestamps = {}
        self.lock = threading.Lock()

    def __clean_cache(self):
        try:
            self.lock.acquire()
            new_dict = {}
            for token in self.__tokens_to_users_and_timestamps:
                pair = self.__tokens_to_users_and_timestamps[token]
                ts = pair[0]
                if ts > datetime.utcnow():  # still fresh enough
                    new_dict[token] = pair
            self.__tokens_to_users_and_timestamps = new_dict
        finally:
            self.lock.release()

    def is_token_good(self, token):
        # purge our check our in-memory token store, then check to see if this token is OK
        # returns the user name if ok
        logging.info("Checking token %s" % (token,))
        try:
            self.lock.acquire()
            if token in self.__tokens_to_users_and_timestamps:
                user_and_ts = self.__tokens_to_users_and_timestamps[token]
                our_expiration_ts = user_and_ts[0]
                our_user = user_and_ts[1]
                our_pwd = user_and_ts[2]
                # if they have a correct token and the expiration time that we stored for it has not yet passed, return username
                if our_expiration_ts > datetime.utcnow():
                    logging.info("Token %s is ok for user %s" % (token, our_user))
                    return our_user, our_pwd
                else:
                    logging.info("Token %s is expired - %s <= %s" % (token, str(our_expiration_ts), str(datetime.utcnow())))
                    return None, None
            logging.info("Token %s not found" % token)
            return None, None
        except Exception as e:
            logging.exception(e)
            return None, None
        finally:
            self.lock.release()

    def set_token_for_user(self, token, username, password):
        self.__clean_cache()
        try:
            self.lock.acquire()
            self.__tokens_to_users_and_timestamps[token] = (datetime.utcnow() + timedelta(minutes=15), username, password)
        finally:
            self.lock.release()

    def get_user_for_token(self, token):
        return self.__tokens_to_users_and_timestamps[token][1]
