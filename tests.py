import unittest
import requests
import mysql
import properties
import os
import utils
import json
import build_spellcheck_filters
import spellchecking
import forecasting
import model
import logging

logging.basicConfig(level=logging.DEBUG)
model_obj = model.Model()

"""
1) Build spellcheck filters
2) launch web service
3) run tests.py
"""


class TestAccountService(unittest.TestCase):

    @staticmethod
    def _load_conf_key_for_pn(pn):
        pairs = model_obj.load_activation_key_pairs()
        for pair in pairs:
            if str(pair.phone_number) == str(pn):
                return pair.activation_key
        return None

    @staticmethod
    def sign_up(username, password, key, phone_number):
        status_code = requests.post(
            "http://localhost:8080/accounts",
            json={"u": username, "p": password, "key": key, "pn": phone_number}
        ).status_code
        if status_code != 200:
            return status_code
        else:
            # activate the account using the PUT method
            # (look up activation key in DB instead of getting it via SMS)
            conf_key = TestAccountService._load_conf_key_for_pn(phone_number)
            return requests.put(
                "http://localhost:8080/accounts",
                json={"u": username, "pn": phone_number, "conf_key": conf_key}
            ).status_code

    def test_valid_signups(self):
        self.assertEqual(TestAccountService.sign_up("test_user", "test_pwd", "valid_new_account_key", "+15555555555"), 200)
        self.assertEqual(TestAccountService.sign_up("test_user_2", "test_pwd_2", "valid_new_account_key", "+15555545555"), 200)

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
        resp = requests.delete("http://localhost:8080/accounts", json={})
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
        assert code == 200, str(code)
        code = TestAccountService.sign_up(TestAlertService.u2, TestAlertService.p2, "valid_new_account_key", TestAlertService.pn2)
        assert code == 200, str(code)
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

    def test_no_sql_injection(self):

        # fetch the current alerts list (there should be 1)
        user_2_alerts = json.loads(requests.get(TestAlertService.EP, auth=(TestAlertService.u2, TestAlertService.p2)).text)
        self.assertEqual(len(user_2_alerts), 1)

        # try to save with some sql in the name - confirm 400
        resp = requests.post(
            TestAlertService.EP,
            auth=(TestAlertService.u, TestAlertService.p),
            json={"id": TestAlertService.u2_alert_id, "name": "drop table users;", "search_terms": ["search", "terms"]}
        )
        self.assertEqual(resp.status_code, 400)

        # make sure that alert's still there
        user_2_alerts = json.loads(requests.get(TestAlertService.EP, auth=(TestAlertService.u2, TestAlertService.p2)).text)
        self.assertEqual(len(user_2_alerts), 1)


class TestUtils(unittest.TestCase):

    def test_encrypt_works(self):
        pwd = "sample_pwd"
        x = utils.encrypt(pwd)
        self.assertTrue(utils.verify(pwd, x))
        self.assertFalse(utils.verify("bad pwd", x))

    def test_generate_new_activation_key(self):
        a1 = utils.generate_new_activation_key()
        a2 = utils.generate_new_activation_key()
        self.assertNotEqual(a1, a2)
        self.assertEqual(len(a1), utils._ACTIVATION_KEY_LENGTH)
        self.assertEqual(len(a2), utils._ACTIVATION_KEY_LENGTH)
        for c in a1:
            self.assertTrue(c in utils._ACTIVATION_KEY_CHARS)
        for c in a2:
            self.assertTrue(c in utils._ACTIVATION_KEY_CHARS)


class TestSpellcheckFilters(unittest.TestCase):

    bloom_filter = None
    cm_sketch = None

    @classmethod
    def setUpClass(cls):
        try:
            os.remove(properties.SEARCH_TERMS_SUGGESTION_TEMP_DB_FILE_PATH)
        except:
            pass
        TestSpellcheckFilters.bloom_filter, TestSpellcheckFilters.cm_sketch = build_spellcheck_filters.build_filters()

    @classmethod
    def tearDownClass(cls):
        build_spellcheck_filters.delete_temp_db()
        build_spellcheck_filters.delete_saved_filters()

    def do_test_bloom_filter(self, bloom_filter):
        self.assertTrue(bloom_filter is not None)
        self.assertTrue(bloom_filter.contains("arc'teryx"))
        self.assertTrue(bloom_filter.contains("palisade pants"))
        self.assertTrue(bloom_filter.contains("costa palapa"))
        self.assertTrue(bloom_filter.contains("breathable hiking pants"))
        self.assertFalse(bloom_filter.contains("a random phrase"))
        self.assertFalse(bloom_filter.contains("another random string"))

    def test_bloom_filter(self):
        self.do_test_bloom_filter(TestSpellcheckFilters.bloom_filter)

    def test_bf_serialization(self):
        build_spellcheck_filters.save_bloom_filter(TestSpellcheckFilters.bloom_filter)
        bf = build_spellcheck_filters.load_bloom_filter()
        self.do_test_bloom_filter(bf)


class TestSpellcheckingService(unittest.TestCase):

    service = None

    @classmethod
    def setUpClass(cls):
        try:
            os.remove(properties.SEARCH_TERMS_SUGGESTION_TEMP_DB_FILE_PATH)
        except:
            pass
        bloom_filter, cm_sketch = build_spellcheck_filters.build_filters()
        build_spellcheck_filters.save_bloom_filter(bloom_filter)
        TestSpellcheckingService.service = spellchecking.SpellcheckingService()

    @classmethod
    def tearDownClass(cls):
        build_spellcheck_filters.delete_temp_db()
        build_spellcheck_filters.delete_saved_filters()

    def test_correct(self):
        service = TestSpellcheckingService.service
        self.assertTrue(service._bloom_filter.contains("arc'teryx"))
        self.assertEqual(service.try_to_correct("arc'teryx"), "arc'teryx")
        self.assertEqual(service.try_to_correct("arcteryx"), "arc'teryx")
        self.assertEqual(service.try_to_correct("arc'terx"), "arc'teryx")
        self.assertEqual(service.try_to_correct("not even close"), None)
        self.assertEqual(service.try_to_correct("air-permeable construction"), "air-permeable construction")
        self.assertEqual(service.try_to_correct("air permeable construction"), "air-permeable construction")
        self.assertEqual(service.try_to_correct("palm leaf roofs"), "palm leaf roofs")
        self.assertEqual(service.try_to_correct("pam leaf roofs"), "palm leaf roofs")
        self.assertEqual(service.try_to_correct("pallm leaf roofs"), "palm leaf roofs")
        self.assertEqual(service.try_to_correct("pal12m leaf roofs"), "palm leaf roofs")
        self.assertEqual(service.try_to_correct("pallm leaf rofs"), "palm leaf roofs")

    def test_through_http_api(self):
        u = "test_spelling"
        p = "spelling"
        TestAccountService.sign_up(u, p, "valid_new_account_key", "+10123456789")
        resp = requests.post(
            "http://localhost:8080/spellcheck",
            auth=(u, p),
            json=["arcterx", "no way this one matches anything, right?", "Costa Plapa 570P"]
        )
        self.assertEqual(resp.status_code, 200)
        results = json.loads(resp.text)
        self.assertEqual(results[0], "arc'teryx")
        self.assertEqual(results[1], "no way this one matches anything, right?")
        self.assertEqual(results[2], "costa palapa 580p")


class TestForecasting(unittest.TestCase):

    s = None
    k = None

    @classmethod
    def setUpClass(cls):
        try:
            os.remove(properties.SEARCH_TERMS_SUGGESTION_TEMP_DB_FILE_PATH)
        except:
            pass
        build_spellcheck_filters.main()
        sets, keys = build_spellcheck_filters.load_forecasting_sets()
        TestForecasting.s = sets
        TestForecasting.k = keys

    def test_pickles(self):
        sets = TestForecasting.s
        keys = TestForecasting.k

        # there should be two sets in our test data
        self.assertEqual(len(sets), 2)

        # all of the mapped values should be integers
        for k in keys:
            self.assertTrue(type(keys[k]) == int)

        # every entry in every set should be mapped to
        for s in sets:
            for entry in s:
                self.assertTrue(entry in keys.values())

    def test_service(self):
        service = forecasting.ForecastingService()
        self.assertEqual(service.get_count_for("provide"), 2)
        self.assertEqual(service.get_count_for("palisade pants"), 1)
        self.assertEqual(service.get_count_for("the north face"), 0)

    def testAPI(self):
        u = "test_forecast"
        p = "forecasts"
        TestAccountService.sign_up(u, p, "valid_new_account_key", "+10123456789")
        resp = requests.post(
            "http://localhost:8080/forecast",
            auth=(u, p),
            json=["palisade pants", "ubuntu linux", "provide"]
        )
        self.assertEqual(resp.status_code, 200)
        results = json.loads(resp.text)
        self.assertEqual(len(results), 4)
        self.assertEqual(results["palisade pants"], 1)
        self.assertEqual(results["ubuntu linux"], 0)
        self.assertEqual(results["provide"], 2)
        print results


def set_up_db():
    try:
        os.remove(properties.SEARCH_TERMS_SUGGESTION_TEMP_DB_FILE_PATH)
    except:
        pass
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
    c.execute(
        "insert into deals (product_name, product_description, url) values (%s, %s, %s)",
        (
            """Arc'teryx Palisade Pant - Men's""",
            """The Arc'teryx Men's Palisade Pants provide an air-permeable construction that's better than any pair of breathable hiking pants you've ever worn.""",
            "x"
        )
    )
    c.execute(
        "insert into deals (product_name, product_description, url) values (%s, %s, %s)",
        (
            "Costa Palapa 580P Sunglasses - Polarized",
            "Palapas are open-sided dwellings made with thatched palm leaf roofs that provide protection from the harsh tropical sun.",
            "x"
        )
    )
    conn.commit()
    conn_pool.return_conn(conn)
    conn_pool.close_all()


def setUpModule():
    set_up_db()


if __name__ == '__main__':
    unittest.main()
