"""
Initialize the langfuse callback handler.

Set up the langfuse callback handler using environment variables.
If the LANGFUSE_HOST environment variable is set, it initializes the handler with
the provided public key, secret key, and host.
Otherwise, it initializes empty handler.
"""

import logging
import os
import uuid

from dotenv import find_dotenv, load_dotenv
from langfuse.callback import CallbackHandler
from langfuse.decorators import langfuse_context

logger = logging.getLogger(__name__)
load_dotenv(find_dotenv())

langfuse_session_id = str(uuid.uuid4())

if os.environ.get("LANGFUSE_HOST"):
    langfuse_context.configure(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        host=os.environ.get("LANGFUSE_HOST"),
        enabled=True,
    )
    langfuse_handler = lambda tags: CallbackHandler(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        host=os.environ.get("LANGFUSE_HOST"),
        tags=tags,
    )
    logger.info("langfuse active")
else:
    langfuse_context.configure(
        enabled=False,
    )
    langfuse_handler = lambda tags: CallbackHandler()
    logger.info("langfuse NOT active")
