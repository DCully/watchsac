import logging
from Queue import Queue
import pymysql
from utils import properties


class DBConnPool(object):
    """ Wraps one sync'd pool of X DB conns - use get() to get them out and put() to put them back. """

    def __init__(self, conn_count=5):
        self.conn_count = conn_count
        self.pool = Queue()
        for x in range(self.conn_count):
            self.pool.put(DBConnPool.__get_db_conn())

    @staticmethod
    def __get_db_conn():
        """ Produces one DB connection - close it using close_db_conn(). """
        return pymysql.connect(
            host=properties.MYSQL_HOST,
            user=properties.MYSQL_USER,
            password=properties.MYSQL_PASSWORD,
            db=properties.MYSQL_DB_NAME
        )

    @staticmethod
    def __close_db_conn(conn):
        """ Attempt to close a DB connection without throwing an exeption if you fail. """
        if conn is not None:
            try:
                conn.close()
            except Exception as e:
                print e

    def get_conn(self):
        conn = self.pool.get()
        if not conn.ping(reconnect=True):
            conn = self.__get_db_conn()
        return conn

    def return_conn(self, conn):
        try:
            logging.debug("attempting commit before returning conn to the pool")
            conn.commit()
            logging.debug("commit went ok")
        except Exception as e:
            logging.error("Commit threw an exception in return_conn")
        finally:
            self.pool.put(conn)

    def close_all(self):
        logging.debug("Closing all DB connections")
        for x in range(self.conn_count):
            DBConnPool.__close_db_conn(self.pool.get())
        logging.debug("All DB connections closed.")
