#!/usr/bin/env python3
"""Thin entrypoint for the modular Piper HTTP server."""

from src.app import create_app, main

__all__ = ["create_app", "main"]


if __name__ == "__main__":
    main()
