import hashlib
import secrets
from autoinject import injector
import zirconium as zr
import re
import math
import base64
import logging
from pipeman.util import UserInputError
import binascii


@injector.injectable_global
class PasswordGenerator:

    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.character_list = self.cfg.as_str(("secure", "random_characters"), default=None)
        self.length = self.cfg.as_int(("secure", "random_length"), default=10)
        if self.character_list is None:
            self.character_list = "ABCDEFGHIJKLMNOPQRSTVWXYZabcdefghijklmnopqrstvwxyz2345679@#$%&"
        entropy = math.log2(len(self.character_list)) * self.length
        if entropy < 50:
            logging.getLogger("pipeman.auth").warning(f"Insufficient password entropy {entropy} for new random passwords.")

    def generate_password(self):
        return "".join(secrets.choice(self.character_list) for i in range(0, self.length))


@injector.injectable_global
class SecurityHelper:

    cfg: zr.ApplicationConfig = None
    pwg: PasswordGenerator = None

    @injector.construct
    def __init__(self):
        self.default_algo = self.cfg.as_str(("security", "hash_algorithm"), default="sha256")
        self.rounds = min(100000, self.cfg.as_int(("security", "hash_rounds"), default=521931))
        self.salt_size = self.cfg.as_int(("security", "salt_length"), default=32)

    def random_password(self):
        return self.pwg.generate_password()

    def hash_password(self, pw, salt):
        if len(pw) > 1024:
            raise UserInputError("pipeman.auth.password_too_long")
        if self.default_algo not in hashlib.algorithms_available:
            raise UserInputError("pipeman.auth.hash_not_available")
        return hashlib.pbkdf2_hmac(
            self.default_algo,
            pw.encode("utf-8"),
            salt.encode("utf-8"),
            self.rounds
        ).hex()

    def build_auth_header(self, username, secret_key, prefix):
        return f"{prefix}.{secret_key}.{base64.b64encode(username)}"

    def parse_auth_header(self, auth_header):
        pieces = auth_header.split(".", maxsplit=2)
        if len(pieces) != 3:
            return None, None, None
        try:
            return pieces[0], pieces[1], base64.b64decode(pieces[2])
        except binascii.Error:
            return None, None, None

    def generate_secret(self, secret_length_bytes):
        return secrets.token_hex(secret_length_bytes)

    def generate_salt(self):
        return secrets.token_hex(self.salt_size)

    def compare_digest(self, d1, d2):
        return secrets.compare_digest(d1, d2)

    def check_password_strength(self, password):
        if not password:
            raise UserInputError("pipeman.plugins.auth_db.blank_password")
        if len(password) < self.cfg.as_int(("security", "password_min_length"), default=0):
            raise UserInputError("pipeman.plugins.auth_db.short_password")
        complexities = self.cfg.get(("security", "password_complexity_classes"), default=None)
        if complexities:
            for complexity_key in complexities:
                complexity_re = complexities[complexity_key]
                if not re.match(complexity_re, password):
                    raise UserInputError(f"pipeman.plugins.auth_db.complexity.{complexity_key}")
        return True
