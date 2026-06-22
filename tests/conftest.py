import os
import sys

# Make the local asok-auth-providers package importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force DEBUG mode and set SECRET_KEY to bypass Asok's production checks.
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-do-not-use-in-prod"
