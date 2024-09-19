import hashlib
import logging
from pathlib import Path
from typing import Dict, Union
from PIL import Image, ImageTk
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class ChatImages(Dict[str, ImageTk.PhotoImage]):
    """
    A dictionary-like class to manage images in a chat application.

    This class extends a dictionary to store images with unique keys generated from file paths
    or URLs. It also maintains a separate dictionary of PIL images.
    """

    def __init__(self):
        """
        Initialize the ChatImages object.

        Sets up the internal dictionary for PIL images.
        """
        super().__init__()
        self._pil_images: Dict[str, Image.Image] = {}

    def create_from_file(self, fn: Union[Path, BytesIO]) -> str:
        """
        Create an image from a file and store it in the dictionary.

        If the image already exists, it returns the existing key.

        :param fn: File path or BytesIO object containing the image data.
        :return: Unique identifier for the stored image.
        :raises ValueError: If the file cannot be opened or read.
        """
        if isinstance(fn, Path):
            with open(fn, "rb") as fd:
                hash = hashlib.md5(fd.read(1024)).hexdigest()
        else:
            hash = hashlib.md5(fn.read(1024)).hexdigest()
            fn.seek(0)
        img = f"img-{hash}"
        if self.get(img):
            logger.debug(f"Img get: {img}")
            return img
        self._pil_images[img] = Image.open(fn)
        self[img] = ImageTk.PhotoImage(self._pil_images[img].resize((150, 150)))
        logger.debug(f"Img Created: {img}")
        return img

    def create_from_url(self, url: str) -> str:
        """
        Create an image from a base64-encoded URL and store it in the dictionary.

        :param url: Base64-encoded URL containing the image data.
        :return: Unique identifier for the stored image.
        :raises ValueError: If the URL cannot be decoded.
        """
        with BytesIO() as buffer:
            buffer.write(base64.b64decode(url.split(",")[-1]))
            buffer.seek(0)
            return self.create_from_file(buffer)

    def get_url(self, name: str) -> str:
        """
        Get a base64-encoded URL for a stored image.

        :param name: Unique identifier for the stored image.
        :return: Base64-encoded URL representing the image.
        :raises KeyError: If the image with the given name does not exist.
        """
        with BytesIO() as buffer:
            self._pil_images[name].save(buffer, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")
