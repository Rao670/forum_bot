import os
import json

# Configuration file for the Automation Bot - SECURED VERSION

# Gmail Credentials (Fetched from GitHub Secrets)
EA_EMAIL = os.environ.get("EA_EMAIL", "")
EA_PASSWORD = os.environ.get("EA_PASSWORD", "")

# API Keys
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "")

# Gemini API Keys from environment variable (JSON list string)
gemini_keys_env = os.environ.get("GEMINI_API_KEYS")
if gemini_keys_env:
    try:
        GEMINI_API_KEYS = json.loads(gemini_keys_env)
    except:
        GEMINI_API_KEYS = [gemini_keys_env]
else:
    # Default to empty list if no keys provided in environment
    GEMINI_API_KEYS = []

# Backward compatibility for scripts that still expect a single key variable.
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""

# Bot Settings
USE_GEMINI = True   # Set to True to use Gemini
USE_CEREBRAS = False# Set to True to use Cerebras (Fallback when Gemini fails)
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL", "")
GOOGLE_CREDENTIALS_FILE = "credentials.json"
MAX_REPLIES_PER_SESSION = 1
TYPING_SPEED_RANGE = (0.05, 0.2) # Seconds per character
WAIT_TIME_RANGE = (5, 15) # Seconds between actions
MANUAL_REVIEW = False# If True, bot waits for user Y/N before posting
SKIP_LOGIN = False # Set to True to skip login for post discovery testing
USE_PROXY = False # Keep False for now to build reputation on direct IP
RESET_SESSION = False # CRITICAL: Keep False to 'Warm Up' the browser profile
