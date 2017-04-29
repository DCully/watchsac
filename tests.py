import unittest
import requests
import mysql
import properties
import os
import utils
import json

# This test suite runs against the actual cherrypy webapp with a mysql back-end running locally behind it.
# It will wipe the database you run it against before every run. Start the web service separately.


class TestAccountService(unittest.TestCase):

    @staticmethod
    def sign_up(username, password, key, phone_number):
        return requests.post(
            "http://localhost:8080/accounts",
            json={"u": username, "p": password, "key": key, "pn": phone_number}
        ).status_code

    def test_valid_signups(self):
        self.assertEqual(TestAccountService.sign_up("test_user", "test_pwd", "valid_new_account_key", "+15555555555"), 201)
        self.assertEqual(TestAccountService.sign_up("test_user_2", "test_pwd_2", "valid_new_account_key", "+15555545555"), 201)

    def test_invalid_passwords(self):
        self.assertEqual(TestAccountService.sign_up("test_user_2", "abcd_abcd_abcd_abcd_abcd_abcd_abcd_abcd_abcd_abcd_", "valid_new_account_key", "+15555545555"), 400)
        self.assertEqual(TestAccountService.sign_up("test_user_2", "a", "valid_new_account_key", "+15555545555"), 400)

    def test_invalid_usernames(self):
        self.assertEqual(TestAccountService.sign_up("abcd_abcd_abcd_abcd_abcd_abcd_abcd_abcd_abcd_abcd_", "awertygfd", "valid_new_account_key", "+15555545555"), 400)
        self.assertEqual(TestAccountService.sign_up("x", "awertygfd", "valid_new_account_key", "+15555545555"), 400)

    def test_invalid_phone_number_1(self):
        self.assertEqual(TestAccountService.sign_up("test_user_2", "test_pwd_2", "valid_new_account_key", "+122345678901"), 400)

    def test_invalid_phone_number_2(self):
        self.assertEqual(TestAccountService.sign_up("test_user_2", "test_pwd_2", "valid_new_account_key", "12345467890"), 400)

    def test_invalid_phone_number_3(self):
        self.assertEqual(TestAccountService.sign_up("test_user_2", "test_pwd_2", "valid_new_account_key", "+123456789"), 400)

    def test_invalid_new_account_key(self):
        self.assertEqual(TestAccountService.sign_up("test_user", "test_pwd", "not_an_ok_key", "+15555555555"), 401)

    def test_inactive_new_account_key(self):
        self.assertEqual(TestAccountService.sign_up("test_user", "test_pwd", "not_valid_new_account_key", "+15555555555"), 401)

    def test_missing_params(self):
        resp = requests.post(
            "http://localhost:8080/accounts",
            json={"u": "valid_username", "p": "valid_pwd", "pn": "+1234567890"}
        )
        self.assertEqual(resp.status_code, 400)
        resp = requests.post(
            "http://localhost:8080/accounts",
            json={"user": "valid_username", "passwd": "valid_pwd", "key": "valid_new_account_key", "pn": "+1234567890"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_other_http_methods_disallowed(self):
        resp = requests.get("http://localhost:8080/accounts")
        self.assertEqual(resp.status_code, 405)
        resp = requests.put("http://localhost:8080/accounts", json={})
        self.assertEqual(resp.status_code, 405)


class TestAlertService(unittest.TestCase):

    EP = "http://localhost:8080/alerts"
    u = "my_alerts_user"
    p = "my_alerts_pwd"
    pn = "+10123456789"
    u2 = "my_alerts_user_2"
    p2 = "my_alerts_pwd_2"
    pn2 = "+10123456789"
    u2_alert_id = None

    @classmethod
    def setUpClass(cls):
        # set up two users, and give one of them an alert
        code = TestAccountService.sign_up(TestAlertService.u, TestAlertService.p, "valid_new_account_key", TestAlertService.pn)
        assert code == 201
        code = TestAccountService.sign_up(TestAlertService.u2, TestAlertService.p2, "valid_new_account_key", TestAlertService.pn2)
        assert code == 201
        name = "I found a sleeping bag!"
        st1 = "feathered friends"
        st2 = "sleeping bag"
        st3 = "down"
        resp = requests.post(
            TestAlertService.EP,
            auth=(TestAlertService.u2, TestAlertService.p2),
            json={"name": name, "search_terms": [st1, st2, st3]}
        )
        assert resp.status_code == 200
        resp = requests.get(
            TestAlertService.EP,
            auth=(TestAlertService.u2, TestAlertService.p2)
        )
        assert resp.status_code == 200
        TestAlertService.u2_alert_id = json.loads(resp.text)[0]["id"]

    def test_positive_normal_flow(self):

        # sign up a new user
        u = TestAlertService.u
        p = TestAlertService.p

        # fetch all alerts - there aren't any
        resp = requests.get(TestAlertService.EP, auth=(u, p))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.text), "[]")
        json_resp = json.loads(resp.text)
        self.assertEqual(len(json_resp), 0)

        # save a new alert
        name = "I found a patagonia wool sweater!"
        st1 = "patagonia"
        st2 = "wool"
        st3 = "sweater"
        resp = requests.post(
            TestAlertService.EP,
            auth=(u, p),
            json={"name": name, "search_terms": [st1, st2, st3]}
        )
        self.assertEqual(resp.status_code, 200)

        # make sure it comes back as one of our alerts now
        resp = requests.get(
            TestAlertService.EP,
            auth=(u, p)
        )
        self.assertEqual(resp.status_code, 200)
        json_resp = json.loads(resp.text)
        self.assertEqual(len(json_resp), 1)
        saved_alert = json_resp[0]
        self.assertEqual(str(name), str(saved_alert["name"]))
        self.assertEqual(len(saved_alert["search_terms"]), 3)
        for st in [st1, st2, st3]:
            self.assertTrue(str(st) in saved_alert["search_terms"])
        first_alert_id = saved_alert["id"]

        # update the first alert
        resp = requests.post(
            TestAlertService.EP,
            auth=(u, p),
            json={"id": first_alert_id, "name": name, "search_terms": [st1, "down"]}
        )
        self.assertEqual(resp.status_code, 200)

        # make sure it comes back changed
        resp = requests.get(
            TestAlertService.EP,
            auth=(u, p)
        )
        self.assertEqual(resp.status_code, 200)
        json_resp = json.loads(resp.text)
        self.assertEqual(len(json_resp), 1)
        saved_alert = json_resp[0]
        self.assertEqual(str(name), str(saved_alert["name"]))
        self.assertEqual(len(saved_alert["search_terms"]), 2)
        for st in [st1, "down"]:
            self.assertTrue(str(st) in saved_alert["search_terms"])

        # save a second alert
        name_2 = "another alert"
        st4 = "ballin"
        st5 = "shoes"
        resp = requests.post(
            TestAlertService.EP,
            auth=(u, p),
            json={"name": name_2, "search_terms": [st4, st5]}
        )
        self.assertEqual(resp.status_code, 200)

        # make sure they're both there now
        resp = requests.get(
            TestAlertService.EP,
            auth=(u, p)
        )
        self.assertEqual(resp.status_code, 200)
        json_resp = json.loads(resp.text)
        self.assertEqual(len(json_resp), 2)
        for alert in json_resp:
            self.assertTrue(alert["name"] in [name, name_2])

        # archive the first alert
        resp = requests.delete(
            TestAlertService.EP + "?id=" + str(first_alert_id),
            auth=(u, p)
        )
        self.assertEqual(resp.status_code, 200)

        # make sure it no longer shows up in the GET response
        resp = requests.get(
            TestAlertService.EP,
            auth=(u, p)
        )
        self.assertEqual(resp.status_code, 200)
        json_resp = json.loads(resp.text)
        self.assertEqual(len(json_resp), 1)
        self.assertEqual(json_resp[0]["name"], name_2)

    def test_nonexistent_user_401(self):
        resp = requests.get(TestAlertService.EP, auth=("user_not_real", TestAlertService.p))
        self.assertEqual(resp.status_code, 401)

    def test_wrong_password_401(self):
        resp = requests.get(TestAlertService.EP, auth=(TestAlertService.u, "wrong_password"))
        self.assertEqual(resp.status_code, 401)

    def test_bad_alert_fields_save_new_400(self):
        resp = requests.post(
            TestAlertService.EP,
            auth=(TestAlertService.u, TestAlertService.p),
            json={"naaame": "yo this is broken", "search_terms": ["borked", "params"]}
        )
        self.assertEqual(resp.status_code, 400)
        resp = requests.post(
            TestAlertService.EP,
            auth=(TestAlertService.u, TestAlertService.p),
            json={"name": "yo this is broken", "srrrch_terms": ["borked", "params"]}
        )
        self.assertEqual(resp.status_code, 400)

    def test_bad_alert_fields_save_update_400(self):
        resp = requests.post(
            TestAlertService.EP,
            auth=(TestAlertService.u2, TestAlertService.p2),
            json={"id": TestAlertService.u2_alert_id, "namaaaaaae": "a new name"}
        )
        self.assertEqual(resp.status_code, 400)

    def test_cant_update_someone_elses_alert_id_400(self):
        resp = requests.post(
            TestAlertService.EP,
            auth=(TestAlertService.u, TestAlertService.p),
            json={"id": TestAlertService.u2_alert_id, "name": "a new name", "search_terms": ["new", "search", "terms"]}
        )
        self.assertEqual(resp.status_code, 400)

    def test_cant_archive_someone_elses_alert_id_400(self):
        resp = requests.delete(TestAlertService.EP + "?id=" + str(TestAlertService.u2_alert_id),
            auth=(TestAlertService.u, TestAlertService.p)
        )
        self.assertEqual(resp.status_code, 400)


class TestUtils(unittest.TestCase):

    def test_encrypt_works(self):
        pwd = "sample_pwd"
        x = utils.encrypt(pwd)
        self.assertTrue(utils.verify(pwd, x))
        self.assertFalse(utils.verify("bad pwd", x))


def set_up_db():
    conn_pool = mysql.DBConnPool()
    cmd = "mysql --user=" + properties.MYSQL_USER + " --password=" + properties.MYSQL_PASSWORD + " < " + os.getcwd() + "/schema.ddl"
    print(cmd)
    os.system(cmd)
    conn = conn_pool.get_conn()
    c = conn.cursor()
    c.execute("insert into new_account_keys "
              "(id, new_account_key, active) "
              "values "
              "(1, 'valid_new_account_key', 1)")
    c.execute("insert into new_account_keys "
              "(id, new_account_key, active) "
              "values "
              "(2, 'not_valid_new_account_key', 0)")
    conn.commit()
    conn_pool.return_conn(conn)
    conn_pool.close_all()


def setUpModule():
    set_up_db()


if __name__ == '__main__':
    unittest.main()
