"""Encrypt/decrypt module."""
import argparse
import base64
from pathlib import Path
from typing import Union

from cryptography.fernet import Fernet, InvalidToken


class Cipher:
    """Encrypt/decrypt data using fernet method."""

    def __init__(self, key: str):
        """Init class with key for encrypt/decrypt."""
        self._fernet = Fernet(base64.urlsafe_b64encode(self._pad(key).encode()))

    @staticmethod
    def _pad(s: str) -> str:
        """Pad string with 'A' to get 32 chars long string."""
        block_size = 32
        return s + (block_size - len(s) % block_size) * "A"

    def data(self, data: bytes, encrypt=False) -> bytes:
        """
        Encrypt/decrypt data.

        :param data:
        :param encrypt: If True, encrypt otherwise decrypt
        :return:
        """
        try:
            return self._fernet.encrypt(data) if encrypt else self._fernet.decrypt(data)
        except InvalidToken:
            raise ValueError("Cannot encrypt or decrypt data. Wrong key or direction?!")

    def file(self, fn: Path, encrypt=False, overwrite=False) -> Union[Path, bytes]:
        """
        Encrypt/Decrypt file content.

        :param overwrite: Overwrite file (True) or return content (False
        :param encrypt: If True, encrypt otherwise decrypt
        :param fn:
        :return:
        """
        with open(fn, "rb+") as fp:
            data = self.data(fp.read(), encrypt=encrypt)
            if overwrite:
                fp.seek(0)
                fp.truncate(0)
                fp.write(data)
                return fn
            else:
                return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tool for encrypt or decrypt using Fernet method of cryptography package."
    )

    parser.add_argument("--key", type=str, required=True, help="decrypt/encrypt key.")
    parser.add_argument("--file", type=str, required=True, help="File to decrypt/encrypt.")
    parser.add_argument("--encrypt", action="store_true", default=False, help="encrypt content")
    parser.add_argument("--overwrite", action="store_true", default=False, help="overwrite content")
    args = parser.parse_args()
    cipher = Cipher(args.key)
    print(cipher.file(args.file, encrypt=args.encrypt, overwrite=args.overwrite))
