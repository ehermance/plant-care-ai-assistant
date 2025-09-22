# tests/conftest.py
import os, sys

# Add the project root (the folder that contains app.py) to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
