"""
Vercel entry point for the staging viewer.

Imports the Flask `app` object from the project-root `app.py` and
re-exports it. Vercel's Python runtime looks for a callable named
`app` — this file provides it without duplicating any code.

Local dev still uses `python app.py` at the project root.
"""
import os
import sys

# Project root is one level above api/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app import app  # noqa: F401  (Vercel picks this up)