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

STORE_PATH = Path(__file__).parent / "../.store_files/images"
STORE_PATH.mkdir(parents=True, exist_ok=True)


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

    def _save_to_store(self, img: str) -> None:
        """
        Save the PIL image to the store directory.

        :param img: The image identifier
        """
        store_path = STORE_PATH / f"{img}.png"
        if self.pil_image[img].mode == "RGBA":
            self.pil_image[img].save(store_path, format="PNG")
        else:
            self.pil_image[img].convert("RGB").save(store_path, format="PNG")

    def _load_from_store(self, img: str) -> bool:
        """
        Try to load an image from the store directory.

        :param img: The image identifier
        :return: True if image was successfully loaded, False otherwise
        """
        store_path = STORE_PATH / f"{img}.png"
        if store_path.exists():
            try:
                self[img] = "Image exists"
                self.pil_image[img] = Image.open(store_path)
                self.pil_image[img].load()
                return True
            except Exception as e:
                del self[img]
                del self.pil_image[img]
                logger.error(f"Failed to load stored image {img}: {e}")
                return False
        return False

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

        # Check if image exists in memory or can be loaded from store
        if self.get(img):
            if image_tk:
                with self._cv:
                    # This is not thread-safety
                    self[img] = ImageTk.PhotoImage(self.pil_image[img].resize(self.get_resize_xy(img)))
            else:
                with self._cv:
                    self[img] = "Image exists"
            return img

        with self._cv:
            # If image doesn't exist, create it
            self.pil_image[img] = Image.open(fn)
            self.pil_image[img].load()
            if image_tk:
                # This is not thread-safety
                self[img] = ImageTk.PhotoImage(self.pil_image[img].resize(self.get_resize_xy(img)))
            else:
                self[img] = "Image exists"

        # Save to store
        self._save_to_store(img)

        logger.info(f"Img Created: {img}")
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
            if image_tk:
                # This is not thread-safety
                self[name] = ImageTk.PhotoImage(self.pil_image[name].resize(self.get_resize_xy(name)))
            else:
                self[name] = "Image exists"
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

    def get(self, img: str) -> Union[ImageTk.PhotoImage, str, None]:
        """
        Get an image from the dictionary, checking storage if not in memory.

        :param img: The image identifier
        :return: The image if found, None if not found
        """
        # First check if image exists in memory
        with self._cv:
            result = super().get(img)
            if result:
                return result

            # If not in memory, try to load from store
            if self._load_from_store(img):
                return self[img]

            # Image not found in memory or storage
            return None


chat_images = ChatImages()
