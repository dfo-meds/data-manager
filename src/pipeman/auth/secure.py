"""Security-related functions that authentication plugins can leverage or override."""
import hashlib
import secrets
from autoinject import injector
import zirconium as zr
import re
import math
import base64
import logging
import typing as t
from pipeman.util import UserInputError
import binascii


@injector.injectable_global
class PasswordGenerator:
    """Responsible for generating a password.

    This default implementation generates passwords using a random selection of characters from a character list.
    """

    cfg: zr.ApplicationConfig = None

    @injector.construct
    def __init__(self):
        self.character_list = self.cfg.as_str(("pipeman", "security", "random_characters"), default=None)
        self.length = self.cfg.as_int(("pipeman", "security", "random_password_length"), default=10)
        if self.character_list is None:
            self.character_list = "ABCDEFGHIJKLMNOPQRSTVWXYZabcdefghijklmnopqrstvwxyz2345679@#$%&"
        entropy = math.log2(len(self.character_list)) * self.length
        if entropy < 50:
            logging.getLogger("pipeman.auth").warning(f"Insufficient password entropy {entropy} for a random password.")

    def generate_password(self) -> str:
        """Generate a random password using secure functions."""
        return "".join(secrets.choice(self.character_list) for i in range(0, self.length))


@injector.injectable_global
class SecurityHelper:
    """Helper functions for security management."""

    cfg: zr.ApplicationConfig = None
    pwg: PasswordGenerator = None

    @injector.construct
    def __init__(self):
        self.log = logging.getLogger("pipeman.auth")
        self.default_algo = self.cfg.as_str(("pipeman", "security", "hash_algorithm"), default="sha256")
        self.rounds = max(100000, self.cfg.as_int(("pipeman", "security", "hash_rounds"), default=521931))
        self.salt_size = self.cfg.as_int(("pipeman", "security", "salt_length"), default=32)
        self.max_password_length = self.cfg.as_int(("pipeman", "security", "max_length"), default=1024)
        self.pepper = self.cfg.as_str(("pipeman", "security", "pepper"), default="")
        self.past_peppers = self.cfg.get(("pipeman", "security", "past_peppers"), default=None)
        self._block_size = None
        if self.default_algo in ("md5", "sha1"):
            self.log.warning(f"Insecure hash algoritm {self.default_algo} used")
        if self.default_algo not in hashlib.algorithms_available:
            self.log.error(f"Hash algorithm {self.default_algo} not available")
        else:
            self._block_size = hashlib.new(self.default_algo).block_size
        if self.salt_size < 32:
            self.log.warning(f"A minimum of 32 bytes for salts is recommended")
        if not self.pepper:
            self.log.warning(f"A secret salt (pepper) is recommended")
        elif len(self.pepper) < 7:
            self.log.warning(f"Peppers are recommended to be at least 7 characters long")
        if self._block_size >= 128 and self.rounds < 210000:
            self.log.warning(f"128-bit PBKDF2 recommends at least 210,000 rounds, (currently {self.rounds})")
        elif 64 <= self._block_size < 128 and self.rounds < 600000:
            self.log.warning(f"64-bit PBKDF2 recommends at least 600,000 rounds, (currently {self.rounds})")
        elif 32 <= self._block_size < 64 and self.rounds < 1300000:
            self.log.warning(f"32-bit PBKDF2 recommends at least 1,300,000 rounds, (currently {self.rounds})")
        elif self._block_size is not None and self._block_size < 32:
            self.log.warning(f"Less than 32-bit PBKDF2 not recommended (currently {self._block_size})")

    def random_password(self) -> str:
        """Generate a random password."""
        return self.pwg.generate_password()

    def is_hash_outdated(self, secret: str, salt: str, existing_hash: str) -> bool:
        """Check if the hash is outdated for a secret that is known to work."""
        try:
            h = self.hash_secret(secret, salt)
            return not self.compare_digest(h, existing_hash)
        except UserInputError:
            return False

    def check_secret(self, secret: str, salt: str, existing_hash: str) -> bool:
        """Check if a secret is valid."""
        try_peppers = [self.pepper]
        if self.past_peppers:
            try_peppers.extend(self.past_peppers)
        for pepper in try_peppers:
            try:
                h = self.hash_secret(secret, salt, _pepper=pepper)
                if self.compare_digest(h, existing_hash):
                    return True
            except UserInputError:
                pass
        return False

    def hash_secret(self, pw: str, salt: str, _pepper: t.Optional[str] = None) -> str:
        """Create a secure hash of a password and salt."""
        if _pepper is None:
            _pepper = self.pepper
        if len(pw) > self.max_password_length:
            raise UserInputError("pipeman.auth.password_too_long")
        if self.default_algo not in hashlib.algorithms_available:
            self.log.error(f"Hash algorithm {self.default_algo} not available")
            raise UserInputError("pipeman.auth.hash_not_available")
        pw += _pepper
        return hashlib.pbkdf2_hmac(
            self.default_algo,
            pw.encode("utf-8"),
            salt.encode("utf-8"),
            self.rounds
        ).hex()

    def build_auth_header(self, username: str, secret_key: str, prefix: str) -> str:
        """Create an Authorization header for keys."""
        return f"{prefix}.{secret_key}.{base64.b64encode(username.encode('utf-8'))}"

    def parse_auth_header(self, auth_header: str) -> t.Tuple[t.Optional[str], t.Optional[str], t.Optional[str]]:
        """Parse an authorization header."""
        pieces = auth_header.split(".", maxsplit=2)
        if len(pieces) != 3:
            return None, None, None
        try:
            return pieces[0], pieces[1], base64.b64decode(pieces[2]).decode('utf-8')
        except (binascii.Error, UnicodeDecodeError):
            return None, None, None

    def generate_secret(self, secret_length_bytes: int) -> str:
        """Generate a random secret of the given length."""
        return secrets.token_hex(secret_length_bytes)

    def generate_salt(self) -> str:
        """Generate a random salt of an appropriate length."""
        return secrets.token_hex(self.salt_size)

    def compare_digest(self, d1: str, d2: str) -> bool:
        """Compare two digests in a secure fashion."""
        if d1 is None or d2 is None:
            return False
        return secrets.compare_digest(d1, d2)

    def check_password_strength(self, password: str) -> bool:
        """Check that the password meets the strength requirements."""
        if not password:
            raise UserInputError("pipeman.auth.blank_password")
        if len(password) < self.cfg.as_int(("pipeman", "security", "password_min_length"), default=0):
            raise UserInputError("pipeman.auth.too_short_password")
        complexities = self.cfg.get(("pipeman", "security", "password_complexity_classes"), default=None)
        if complexities:
            for complexity_key in complexities:
                complexity_re = complexities[complexity_key]
                if not re.match(complexity_re, password):
                    raise UserInputError(f"pipeman.auth.complexity.{complexity_key}")
        return True
