"""
Vercel entry point for the drain.
Imports the HTTP handler from the project-root cron.py.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cron import handler  # noqa: F401