from build_spellcheck_filters import load_forecasting_sets
from threading import Lock
from datetime import datetime, timedelta
import logging


class ForecastingService(object):

    __RELOAD_INTERVAL_HOURS = 1

    def __init__(self):
        self.lock = Lock()
        self.created = datetime.utcnow() - timedelta(hours=ForecastingService.__RELOAD_INTERVAL_HOURS + 2)
        self.__load_filters()

    def __load_filters(self):
        try:
            logging.info("Attempting to load forecasting data from disk")
            self.lock.acquire()
            if self.created < datetime.utcnow() - timedelta(hours=1):
                self.created = datetime.utcnow()
                self._sets, self._keys = load_forecasting_sets()
            logging.info("Disk forecasting data load success")
        except Exception as e:
            logging.exception(e)
        finally:
            self.lock.release()

    def __get_data(self):
        if self.created < datetime.utcnow() - timedelta(hours=1):
            self.__load_filters()
            self.created = datetime.utcnow()
        return self._keys, self._sets

    def get_count_for(self, phrase):
        phrase = phrase.lower()
        keys, sets = self.__get_data()
        if phrase not in keys:
            return 0
        else:
            phrase_id = keys[phrase]
            count = 0
            for s in sets:
                if phrase_id in s:
                    count += 1
            return count

    def get_count_for_all(self, phrases):
        lowercased_phrases = [phrase.lower() for phrase in phrases]
        keys, sets = self.__get_data()
        phrase_ids = []
        for phrase in lowercased_phrases:
            if phrase not in keys:
                return 0
            else:
                phrase_ids.append(keys[phrase])
        count = 0
        for s in sets:
            all_in = True
            for phrase_id in phrase_ids:
                if phrase_id not in s:
                    all_in = False
                    break
            if all_in:
                count += 1
        return count
