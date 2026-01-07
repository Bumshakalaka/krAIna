"""Tools package for krAIna.

This package contains various tools that can be used by assistants for
different functionalities like image analysis, text processing, audio
transcription, and more.
"""

# Import early so we can patch it before langchain_mcp_adapters uses it
import httpx  # noqa: F401

# Patch httpx to use the system CA bundle
import httpx_system_certs  # noqa: F401
