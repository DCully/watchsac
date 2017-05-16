from passlib.hash import pbkdf2_sha512
import random

_ACTIVATION_KEY_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
_ACTIVATION_KEY_LENGTH = 6


def is_valid_phone_number(phone_number):
    phone_number = str(phone_number)
    if len(phone_number) != 12:
        return False
    if phone_number[0] != "+":
        return False
    for c in phone_number[1:]:
        if c not in "0123456789":
            return False
    return True


def is_valid_username(username):
    if len(username) < 5 or len(username) > 40:
        return False
    return True


def is_valid_password(password):
    if len(password) < 8 or len(password) > 40:
        return False
    return True


def encrypt(password):
    return pbkdf2_sha512.hash(password)


def verify(password_attempt, hash):
    return pbkdf2_sha512.verify(password_attempt, hash)


def generate_new_activation_key():
    return "".join([_ACTIVATION_KEY_CHARS[random.randint(0, len(_ACTIVATION_KEY_CHARS) - 1)] for x in range(_ACTIVATION_KEY_LENGTH)])
