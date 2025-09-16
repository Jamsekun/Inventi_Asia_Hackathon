import sys
import os

# Add the parent directory to the path so we can import backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.main import app