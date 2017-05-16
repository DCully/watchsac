import logging
from datetime import datetime, timedelta
from threading import Lock

from scheduled_jobs.build_spellcheck_filters import load_bloom_filter


# TODO - improve this thing's performance (runs kind of slow and edit distance is not a great spelling error metric)


class SpellcheckingService(object):

    __ALT_CHARS = "abcdefghijklmnopqrstuvwxyz'-0123456789"
    __RELOAD_INTERVAL_HOURS = 1

    def __init__(self):
        self.lock = Lock()
        self.created = datetime.utcnow() - timedelta(hours=SpellcheckingService.__RELOAD_INTERVAL_HOURS + 2)
        self.__load_filters()

    def __load_filters(self):
        try:
            logging.info("Attempting to load filters from disk")
            self.lock.acquire()
            if self.created < datetime.utcnow() - timedelta(hours=1):
                self.created = datetime.utcnow()
                self._bloom_filter = load_bloom_filter()
            logging.info("Disk filter load success")
        except Exception as e:
            logging.exception(e)
        finally:
            self.lock.release()

    def __get_bf(self):
        if self.created < datetime.utcnow() - timedelta(hours=1):
            self.__load_filters()
            self.created = datetime.utcnow()
        return self._bloom_filter

    def __yield_1_edits_lists(self, word):
        """ TODO - make this be 2-edits, not just one... how can we make that run fast enough?. """
        # adapted from:  http://norvig.com/spell-correct.html
        # splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        # deletes = [L + R[1:] for L, R in splits if R]
        # transposes = [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]
        # replaces = [L + c + R[1:] for L, R in splits if R for c in letters]
        # inserts = [L + c + R for L, R in splits for c in letters]
        splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        yield [L + c + R for L, R in splits for c in SpellcheckingService.__ALT_CHARS]  # inserts
        yield [L + R[1:] for L, R in splits if R]  # deletes
        yield [L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1]  # transposes
        yield [L + c + R[1:] for L, R in splits if R for c in SpellcheckingService.__ALT_CHARS]  # replaces

    def __yield_2_edits(self, phrase):
        for edit_list in self.__yield_1_edits_lists(phrase):
            for edit in edit_list:
                for one_edits_list in self.__yield_1_edits_lists(edit):
                    yield one_edits_list

    def try_to_correct(self, phrase):
        """ This method tries to 'correct' an inputted phrase to some other phrase nearby in the corpus. It returns a corrected phrase, or None. """
        phrase = phrase.lower()
        bf = self.__get_bf()
        if bf.contains(phrase):
            logging.debug("Found phrase %s in bloom filter - exact match" % (phrase,))
            return phrase
        for edits in self.__yield_2_edits(phrase):
            for edit in edits:
                if bf.contains(edit):
                    logging.debug("Phrase %s corrects to %s" % (phrase, edit))
                    return edit
        logging.debug("Phrase %s uncorrectable" % phrase)
        return None
