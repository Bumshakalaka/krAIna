"""Initialize the langfuse callback handler.

Set up the langfuse callback handler using environment variables.
If the LANGFUSE_HOST environment variable is set, it initializes the handler with
the provided public key, secret key, and host.
Otherwise, it initializes empty handler.
"""

import logging
import os
import subprocess
import uuid

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

logger = logging.getLogger(__name__)

if os.environ.get("LANGFUSE_HOST"):
    try:
        sha = (
            subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
            .stdout.strip()[:7]
            .lower()
        )
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        app_sha = f"{branch}:{sha}"
    except Exception as e:
        logger.warning(f"Could not determine git SHA or branch: {e}")
        app_sha = ""

    Langfuse(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY"),
        host=os.environ.get("LANGFUSE_HOST"),
        flush_at=2,
        release=app_sha,
    )

    logger.info("langfuse active")
else:
    Langfuse(
        tracing_enabled=False,
    )
    logger.info("langfuse NOT active")

langfuse_session_id = str(uuid.uuid4())
langfuse_user_id = os.environ.get("USER", "unknown")

langfuse_handler = CallbackHandler()
