import hashlib
import logging
import tempfile
import threading
from pathlib import Path
from typing import Dict, Union, Tuple

import requests
from PIL import Image, ImageTk, ImageChops
import base64
from io import BytesIO

logger = logging.getLogger(__name__)


class ChatImages(Dict[str, ImageTk.PhotoImage | str]):
    """
    A dictionary-like class to manage images in a chat application.

    This class extends a dictionary to store images with unique keys generated from file paths
    or URLs. It also maintains a separate dictionary of PIL images.
    """

    _lock: threading.Lock = threading.Lock()
    _cv: threading.Condition = threading.Condition(_lock)

    def __init__(self):
        """
        Initialize the ChatImages object.

        Sets up the internal dictionary for PIL images.
        """
        super().__init__()
        self.pil_image: Dict[str, Image.Image] = {}

    def create_from_file(self, fn: Union[Path, BytesIO], name: str = None, image_tk=True) -> str:
        """
        Create an image from a file and store it in the dictionary.

        If the image already exists, it returns the existing key.

        :param fn: File path or BytesIO object containing the image data.
        :param name: Name of the image, None if we'd like to create new one
        :param image_tk: Generate ImageTk.PhotoImage (tkinter and GUI required) or not
        :return: Unique identifier for the stored image.
        :raises ValueError: If the file cannot be opened or read.
        """
        with self._cv:
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
            self.pil_image[img].load()
            if image_tk:
                # This is not thread-safety
                self[img] = ImageTk.PhotoImage(self.pil_image[img].resize(self.get_resize_xy(img)))
            else:
                self[img] = "Image exists"
            logger.debug(f"Img Created: {img}")
            return img

    def get_resize_xy(self, name: str, max_height=150) -> Tuple[int, int]:
        """
        Get the resized dimensions for an image.

        This function calculates the new dimensions for an image to ensure that its height
        does not exceed 150 pixels, maintaining the aspect ratio.

        :param name: The name of the image to resize.
        :param max_height:
        :return: A tuple containing the new width and height of the image.
        """
        div = 1
        if self.pil_image[name].height > max_height:
            div = max(self.pil_image[name].height, self.pil_image[name].width) // max_height
        return self.pil_image[name].width // div, self.pil_image[name].height // div

    def create_from_url(self, url: str, name: str = None, image_tk=True) -> str:
        """
        Create an image from a URL, file path, or base64 string.

        This function fetches image data from a given URL, file path, or base64 encoded string,
        and creates an image object. If a name is provided and already exists, it returns the name.

        :param url: The URL, file path, or base64 encoded string of the image.
        :param name: Optional name for the image. If provided and exists, the existing name is returned.
        :param image_tk: Boolean flag to indicate if the image should be processed for Tkinter.
        :return: The name of the created image.
        :raises ValueError: If the URL scheme is not recognized.
        """
        if name and self.get(name):
            logger.debug(f"Img get: {name}")
            return name
        with BytesIO() as buffer:
            if url.startswith("https://"):
                buffer.write(requests.get(url).content)
            elif url.startswith("file://"):
                with open(Path(url.replace("file://", "")), "rb") as fd:
                    buffer.write(fd.read())
            else:
                buffer.write(base64.b64decode(url.split(",")[-1]))
            buffer.seek(0)
            return self.create_from_file(buffer, name, image_tk)

    def _invert_rgba_image_chops(self, img):
        """
        Invert the colors of an RGBA image while preserving the alpha channel.

        This function creates a white image of the same size as the input image,
        splits the input image into its RGB and alpha components, inverts the RGB
        colors using ImageChops, and then merges the inverted RGB with the original
        alpha channel to produce the final image.

        :param img: The input image in RGBA format to be inverted.
        :return: An RGBA image with inverted colors and original alpha channel.
        """
        # Create a white image of the same size
        white = Image.new("RGB", img.size, (255, 255, 255))

        # Split alpha channel
        r, g, b, a = img.split()
        rgb = Image.merge("RGB", (r, g, b))

        # Invert using ImageChops
        inverted_rgb = ImageChops.difference(white, rgb)

        # Merge back with original alpha
        inverted_img = Image.merge("RGBA", (*inverted_rgb.split(), a))

        return inverted_img

    def get_url(self, name: str, inverted=False) -> str:
        """
        Get a base64-encoded URL for a stored image.

        :param name: Unique identifier for the stored image.
        :param inverted: invert background color
        :return: Base64-encoded URL representing the image.
        :raises KeyError: If the image with the given name does not exist.
        """
        with BytesIO() as buffer:
            if inverted:
                temp_ = self._invert_rgba_image_chops(self.pil_image[name])
                temp_.save(buffer, format="PNG")
            else:
                self.pil_image[name].save(buffer, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")

    def dump_to_tempfile(self, name: str, resize=True):
        """
        Save an image to a temporary file with optional resizing.

        This function saves an image from the `pil_image` attribute to a temporary file with a ".png" suffix.
        The image can be optionally resized before saving.

        :param name: The key to the image in the `pil_image` attribute.
        :param resize: Boolean flag indicating whether the image should be resized. Defaults to True.
        :return: The name of the temporary file where the image is saved.
        """
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as fd:
            if resize:
                self.pil_image[name].resize(self.get_resize_xy(name)).save(fd, format="PNG")
            else:
                self.pil_image[name].save(fd, format="PNG")
            fd.seek(0)
            return fd.name


chat_images = ChatImages()
