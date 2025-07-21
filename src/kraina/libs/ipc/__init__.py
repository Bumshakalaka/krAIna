"""Inter-Process Communication (IPC) module for krAIna application.

This module provides inter-process communication capabilities for the krAIna
application, allowing external processes to communicate with the main
application through a socket-based protocol.

The IPC system consists of:
- A host component that listens for incoming connections
- A client component that can send commands to the host
- A base module containing shared constants and utilities

The communication protocol uses a simple text-based format with the following
structure: APP_KEY|COMMAND|PARAMETERS where parameters are base64-encoded JSON.

Supported operations include:
- Sending commands to the main application
- Receiving responses and acknowledgments
- Thread-safe communication between processes
- Automatic connection management and cleanup
"""
