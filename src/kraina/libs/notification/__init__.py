"""Notification system package for platform-specific desktop notifications.

This package provides a unified interface for displaying desktop notifications
across different operating systems. It includes platform-specific implementations
for Windows and Linux, with a factory pattern to automatically select the
appropriate implementation based on the current platform.

The package consists of:
- MyNotifyInterface: Abstract base class defining the notification contract
- MyNotify: Factory function for creating platform-specific notifications
- MyLinuxNotify: Linux implementation using DBus interface
- MyWindowsNotify: Windows implementation using Windows Toasts API
"""
