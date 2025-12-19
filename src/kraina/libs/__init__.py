"""Core library modules for the krAIna application.

This package contains essential utility modules and libraries used throughout
the krAIna application. It provides functionality for database operations,
inter-process communication, clipboard management, notifications, image
processing, language model interactions, and various utility functions.
"""

# Import early so we can patch it before langchain_mcp_adapters uses it
import httpx  # noqa: F401

# Patch httpx to use the system CA bundle
import httpx_system_certs  # noqa: F401
