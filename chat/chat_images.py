import hashlib
import logging
from pathlib import Path
from typing import Dict, Union, Tuple
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
        self.pil_image: Dict[str, Image.Image] = {}

    def create_from_file(self, fn: Union[Path, BytesIO], name: str = None) -> str:
        """
        Create an image from a file and store it in the dictionary.

        If the image already exists, it returns the existing key.

        :param fn: File path or BytesIO object containing the image data.
        :param name: Name of the image, None if we'd like to create new one
        :return: Unique identifier for the stored image.
        :raises ValueError: If the file cannot be opened or read.
        """
        if not name:
            if isinstance(fn, Path):
                with open(fn, "rb") as fd:
                    hash = hashlib.md5(fd.read(1024)).hexdigest()
            else:
                hash = hashlib.md5(fn.read(1024)).hexdigest()
                fn.seek(0)
            img = f"img-{hash}"
        else:
            img = name
        if self.get(img):
            logger.debug(f"Img get: {img}")
            return img
        self.pil_image[img] = Image.open(fn)
        self[img] = ImageTk.PhotoImage(self.pil_image[img].resize(self.get_resize_xy(img)))
        logger.debug(f"Img Created: {img}")
        return img

    def get_resize_xy(self, name: str) -> Tuple[int, int]:
        """
        Get the resized dimensions for an image.

        This function calculates the new dimensions for an image to ensure that its height
        does not exceed 150 pixels, maintaining the aspect ratio.

        :param name: The name of the image to resize.
        :return: A tuple containing the new width and height of the image.
        """
        div = 1
        if self.pil_image[name].height > 150:
            div = max(self.pil_image[name].height, self.pil_image[name].width) // 150
        return self.pil_image[name].width // div, self.pil_image[name].height // div

    def create_from_url(self, url: str, name: str = None) -> str:
        """
        Create an image from a base64-encoded URL and store it in the dictionary.

        :param url: Base64-encoded URL containing the image data.
        :param name: Name of the image, None if we'd like to create new one
        :return: Unique identifier for the stored image.
        :raises ValueError: If the URL cannot be decoded.
        """
        if name and self.get(name):
            logger.debug(f"Img get: {name}")
            return name
        with BytesIO() as buffer:
            buffer.write(base64.b64decode(url.split(",")[-1]))
            buffer.seek(0)
            return self.create_from_file(buffer, name)

    def get_url(self, name: str) -> str:
        """
        Get a base64-encoded URL for a stored image.

        :param name: Unique identifier for the stored image.
        :return: Base64-encoded URL representing the image.
        :raises KeyError: If the image with the given name does not exist.
        """
        with BytesIO() as buffer:
            self.pil_image[name].save(buffer, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")


chat_images = ChatImages()
