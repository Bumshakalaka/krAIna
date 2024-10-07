import functools
import json
import pickle
from pathlib import Path
from typing import Dict

from dotenv import find_dotenv, load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool, StructuredTool

from tools.base import logger

load_dotenv(find_dotenv())



class VectorSearchInput(BaseModel):
    query: str = Field(description="Query the document. The query must be short, well-structured for RAG")
    file_path: str = Field(description="local file to query")


def vector_search(assistant, query: str, file_path:str):
    store_files = Path(__file__).parent / ".." / ".store_files"
    store_files.mkdir(exist_ok=True)
    name = Path(file_path).stem
    if (store_files / f"{name}.pkl").exists():
        vector_store = InMemoryVectorStore.from_documents([], OpenAIEmbeddings(model="text-embedding-ada-002"))
        with open(store_files / f"{name}.pkl", 'rb') as fd:
            vector_store.store = pickle.load(fd)
        logger.info(f"{name} file known and recall")
    else:
        logger.info(f"{name} file not known and will be processed first time")
        loader = PyPDFLoader(file_path, extraction_mode="plain", extract_images=False)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=200)
        docs = loader.load_and_split(text_splitter=text_splitter)
        vector_store = InMemoryVectorStore.from_documents(docs, OpenAIEmbeddings(model="text-embedding-ada-002"))
        with open(store_files / f"{name}.pkl", 'wb') as fd:
            pickle.dump(vector_store.store, fd, pickle.HIGHEST_PROTOCOL)
    results = vector_store.similarity_search(query, k=10)
    ret = []
    for result in results:
        ret.append(dict(content=result.page_content, **result.metadata))
    return json.dumps(ret)

def init_vector_search(tool_setting: Dict) -> BaseTool:
    """
    Initialize the text-to-image tool with the given settings.

    This function creates a StructuredTool instance for generating images
    from text descriptions using the specified tool settings.

    :param tool_setting: Dictionary containing settings for the tool,
                         including the 'assistant' key with 'force_api'.
    :return: An instance of BaseTool configured for text-to-image generation.
    """
    return StructuredTool.from_function(
        func=functools.partial(
            vector_search,
            tool_setting["assistant"]
        ),
        name="vector-search",
        description="Load and split document and upload to vector database and use semantic search to find answer on user query. The result is list of dict(content, page, source) which must be structure and rephrase",
        args_schema=VectorSearchInput,
        return_direct=False,
    )
