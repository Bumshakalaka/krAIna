import json
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict

from langchain_community.document_loaders import JoplinLoader
from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import MarkdownTextSplitter
from pydantic import BaseModel, Field

from libs.llm import embedding, map_model
from tools.base import logger


class JoplinSearchInput(BaseModel):
    query: str = Field(
        description="Query the Joplin, a local note-taking app. The query must be short, well-structured for RAG"
    )
    k: int = Field(
        description="How many top similar results to return. The first one, is most valuable result. Depends on user need, MAX=15"
    )


def joplin_search(query: str, k: int = 4, model: str = "text-embedding-ada-002", force_api: str = None):
    """
    Perform a search on Joplin notes using a specified language model.

    This function searches through Joplin notes, using embeddings to find the most relevant content.
    It supports caching of processed data to improve performance on repeated queries.

    :param query: The search query string to find relevant notes.
    :param k: The number of top results to return, defaults to 4.
    :param model: The language model to be used for generating embeddings.
    :param force_api: The API type to be enforced for embedding generation.
    :return: A JSON string containing the source and query results.
    :raises KeyError: If the JOPLIN_API_KEY environment variable is not set.
    :raises FileNotFoundError: If the specified file paths do not exist.
    :raises ValueError: If the date format in the document metadata is incorrect.
    """
    store_files = Path(__file__).parent / ".." / ".store_files"
    store_files.mkdir(exist_ok=True)

    model = map_model(model, force_api)

    embed = embedding(force_api_type=force_api, model=model)

    loader = JoplinLoader(access_token=os.environ["JOPLIN_API_KEY"])
    docs = loader.load()

    mktime = max(datetime.strptime(doc.metadata["updated_time"], "%Y-%m-%d %H:%M:%S").timestamp() for doc in docs)

    store_file_name = f"{mktime}_joplin_{model}_MarkdownTextSplitter"

    if (store_files / f"{store_file_name}.pkl").exists():
        logger.info(f"{store_file_name} file is known and store will be recreated")

        vector_store = InMemoryVectorStore.from_documents([], embed)
        # Recall the stored structure
        with open(store_files / f"{store_file_name}.pkl", "rb") as fd:
            vector_store.store = pickle.load(fd)
    else:
        logger.info(f"{store_file_name} file not known and store will be created")

        splitter = MarkdownTextSplitter(chunk_size=3000, chunk_overlap=50)
        docs = loader.load_and_split(text_splitter=splitter)

        vector_store = InMemoryVectorStore.from_documents(docs, embed)
        # Remove previous version
        for ff in Path(store_files).glob("*joplin*"):
            ff.unlink()
        # Store the store structure for further use
        with open(store_files / f"{store_file_name}.pkl", "wb") as fd:
            pickle.dump(vector_store.store, fd, pickle.HIGHEST_PROTOCOL)

    results = vector_store.similarity_search_with_score(query, k=k)
    ret = {"source": "Joplin", "query_results": []}
    for result, score in results:
        if score < 0.7:
            # remove results which are very low connected
            continue
        result.metadata.pop("source", None)  # remove source
        ret["query_results"].append(dict(content=result.page_content, **result.metadata))
    return json.dumps(ret)


def init_joplin_search(tool_setting: Dict) -> BaseTool:
    """
    Initialize a vector search tool for Joplin app with the given settings.

    This function configures a structured tool for performing vector searches.
    It uses a specified model to load, split, and upload documents to a vector
    database, enabling semantic search for user queries.

    :param tool_setting: A dictionary containing configuration for the tool,
                         including model and assistant API settings.
    :return: An instance of a structured tool configured for vector search.
    """
    return StructuredTool.from_function(
        func=(lambda model, force_api: lambda query, k=4: joplin_search(query, k, model, force_api))(
            model=tool_setting.get("model", "text-embedding-ada-002"),
            force_api=tool_setting["assistant"].force_api,
        ),
        name="joplin-search",
        description="Search Joplin, a local note-taking app. "
        "Use semantic search by utilize vector database to find answer on user query. "
        "The result is JSON {'source': file_path, 'query_results': [dict(content, page, other_metadata), dict(content, page, other_metadata),...]} "
        "which must be structure and rephrase",
        args_schema=JoplinSearchInput,
        return_direct=False,
    )
