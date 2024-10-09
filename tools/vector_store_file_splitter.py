"""Vector store splitters."""
import re
from typing import List, Dict, Type

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from dataclasses import dataclass

FILE_SPLITTERS: Dict[str, Type["FileSplitter"]] = {}

def get_splitter(file_path: str) -> Type["FileSplitter"]:
    """
    Retrieve the appropriate FileSplitter for a given file path.

    This function matches the file path against registered file patterns
    in FILE_SPLITTERS and returns the FileSplitter with the highest priority.

    :param file_path: The path of the file for which a splitter is needed.
    :return: The FileSplitter class that matches the file path pattern.
    :raises AttributeError: If no matching splitter is found for the file path.
    """
    ret = []
    for _, obj in FILE_SPLITTERS.items():
        if re.match(obj.file_pattern_re, file_path):
            ret.append([obj.priority, obj])
    if not ret:
        raise AttributeError(f"No splitter found for file: '{file_path}'. Supported splitters: {list(FILE_SPLITTERS.keys())}")

    return sorted(ret, key=lambda x: x[0])[-1][1]

@dataclass(eq=False)
class FileSplitter:
    """
    Base class for file splitters, adding subclasses to a global registry.

    This class serves as a base for specific file splitters. Subclasses are automatically
    registered in the `FILE_SPLITTERS` dictionary unless their class name starts with '_'.

    :param file_pattern_re: Regular expression pattern for matching file types.
    :param priority: Priority of the file splitter.
    """
    file_pattern_re: str = None
    priority: int = None

    def __init_subclass__(cls, **kwargs):
        """
        Automatically register subclasses in `FILE_SPLITTERS`.

        Subclasses with names not starting with '_' are added to the global `FILE_SPLITTERS`
        dictionary, allowing for easy access and management of different file splitters.
        """
        super().__init_subclass__(**kwargs)
        if not cls.__name__.startswith("_"):
            FILE_SPLITTERS[cls.__name__] = cls

    @classmethod
    def split(cls, file_path: str) -> List[Document]:
        """
        Split a file into documents.

        This method should be implemented by subclasses to define specific splitting logic.

        :param file_path: Path to the file to be split.
        :return: A list of Document objects resulting from the split.
        :raises NotImplementedError: If the method is not implemented by a subclass.
        """
        raise NotImplementedError()


@dataclass(eq=False)
class PdfSplitter(FileSplitter):
    """
    Splits PDF files into documents.

    This class provides functionality to load and split PDF files into smaller
    document chunks using a text splitter.
    """
    file_pattern_re = r".+\.pdf"
    priority: int = 1

    @classmethod
    def split(cls, file_path: str) -> List[Document]:
        """
        Split a PDF file into documents.

        Loads a PDF file and splits it into smaller chunks using a character-based
        text splitter for further processing.

        :param file_path: Path to the PDF file to be split.
        :return: A list of Document objects resulting from the split.
        """
        loader = PyPDFLoader(file_path, extraction_mode="plain", extract_images=False)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=50, length_function=len)
        return loader.load_and_split(text_splitter=text_splitter)


@dataclass(eq=False)
class TxtSplitter(FileSplitter):
    """
    Splits text and log files into documents.

    This class provides functionality to load and split text-based files
    into smaller document chunks using a text splitter.
    """
    file_pattern_re = r".+\.(txt|log)"
    priority: int = 1

    @classmethod
    def split(cls, file_path: str) -> List[Document]:
        """
        Split a text or log file into documents.

        Loads a text or log file and splits it into smaller chunks using a character-based
        text splitter for further processing.

        :param file_path: Path to the text or log file to be split.
        :return: A list of Document objects resulting from the split.
        """
        loader = TextLoader(file_path)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=50)
        return loader.load_and_split(text_splitter=text_splitter)


