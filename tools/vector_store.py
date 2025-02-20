import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict

from langchain_core.tools import BaseTool, StructuredTool
from langchain_core.vectorstores import InMemoryVectorStore
from pydantic import BaseModel, Field

from libs.llm import embedding, map_model
from libs.utils import str_shortening
from tools.base import logger
from tools.vector_store_file_splitter import get_splitter


class VectorSearchInput(BaseModel):
    query: str = Field(description="Query the file. The query must be short, well-structured for RAG")
    file_path: str = Field(description="local file to query")
    k: int = Field(
        description="How many top similar results to return. "
        "The first one, is most valuable result. Depends on user need, MAX=15"
    )


def vector_search(query: str, file_path: str, k: int = 4, model: str = "embed", force_api: str = None):
    """
    Perform a vector search on a document using a specified model and API.

    This function processes a document file, creates or loads an embedded vector store,
    and performs a similarity search based on the provided query.

    :param query: The search query string.
    :param file_path: The path to the document file to be processed.
    :param k: The number of top similar results to return (default is 1).
    :param model: The name of the model to be used for embedding.
    :param force_api: The API type for embedding.
    :return: A JSON string containing the source file path and the query results.
    """
    splitter = get_splitter(file_path)

    store_files = Path(__file__).parent / ".." / ".store_files"
    store_files.mkdir(exist_ok=True)
    mktime = datetime.fromtimestamp(Path(file_path).stat().st_mtime).strftime("%Y%m%d_%H%M%S")
    store_file_name = f"{mktime}_{Path(file_path).name}_" + model.replace("/", "_") + splitter.__name__

    model = map_model(model, force_api)

    embed = embedding(force_api_type=force_api, model=model)

    if (store_files / f"{store_file_name}.pkl").exists():
        logger.info(f"{store_file_name} file is known and store will be recreated")

        vector_store = InMemoryVectorStore.from_documents([], embed)
        # Recall the stored structure
        with open(store_files / f"{store_file_name}.pkl", "rb") as fd:
            vector_store.store = pickle.load(fd)
    else:
        logger.info(f"{store_file_name} file not known and store will be created")

        docs = splitter.split(file_path)

        vector_store = InMemoryVectorStore.from_documents(docs, embed)
        # Store the store structure for further use
        with open(store_files / f"{store_file_name}.pkl", "wb") as fd:
            pickle.dump(vector_store.store, fd, pickle.HIGHEST_PROTOCOL)
    # TODO: reduce based on keywords
    results = vector_store.similarity_search_with_score(query, k=k)
    # TODO: re-rank
    ret = {"source": file_path, "query_results": []}
    for result, score in results:
        if score < 0.3:
            # remove results which are very low connected
            logger.warning(f"Remove because of score {score} < 0.3 - {str_shortening(result.page_content)}")
            continue
        result.metadata.pop("source", None)  # remove source
        ret["query_results"].append(dict(content=result.page_content, **result.metadata))
    return json.dumps(ret)


def init_vector_search(tool_setting: Dict) -> BaseTool:
    """
    Initialize a vector search tool with the given settings.

    This function configures a structured tool for performing vector searches.
    It uses a specified model to load, split, and upload documents to a vector
    database, enabling semantic search for user queries.

    :param tool_setting: A dictionary containing configuration for the tool,
                         including model and assistant API settings.
    :return: An instance of a structured tool configured for vector search.
    """
    return StructuredTool.from_function(
        func=(
            lambda model, force_api: lambda query, file_path, k=4: vector_search(query, file_path, k, model, force_api)
        )(
            model=tool_setting.get("model", "embed"),
            force_api=tool_setting["assistant"].force_api,
        ),
        name="vector-search",
        description="Load and split document and upload to vector database and "
        "use semantic search to find answer on user query. "
        "The result is JSON {'source': file_path, 'query_results': [dict(content, page, other_metadata), "
        "dict(content, page, other_metadata),...]}"
        "which must be structure and rephrase",
        args_schema=VectorSearchInput,
        return_direct=False,
    )
