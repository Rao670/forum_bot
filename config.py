import os
import json

# Configuration file for the Automation Bot

# Gmail Credentials
EA_EMAIL = os.environ.get("EA_EMAIL", "raoathar670@gmail.com")
EA_PASSWORD = os.environ.get("EA_PASSWORD", "Sahibdad670!")

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
    GEMINI_API_KEYS = [
        "AIzaSyDi2D0hA3pZ8b4hIAEiRi8RsVxAu8gR6_E",
        "AIzaSyAQD9uIqK8KYmNcd5j9cJc6cSPYK1_smu8", 
        "AIzaSyBBjnEpVzo9VH7nfFHOFsW-0KsmUmqYdhs",
        "AIzaSyCxh_ANVqQVOAaK6LpVGshV53ungwIhK9E",
        "AIzaSyAzWAWbkqHSY5IteOS-G83gCL6r7TG7tIs",
    ]

# Bot Settings
USE_GEMINI = True   # Set to True to use Gemini
USE_CEREBRAS = False# Set to True to use Cerebras (Fallback when Gemini fails)
GOOGLE_SHEET_URL = os.environ.get("GOOGLE_SHEET_URL", "https://docs.google.com/spreadsheets/d/1SjFn694SBeLi0G_Sjlks4WyKjBg601gek7ohXLYXNWI/edit")
GOOGLE_CREDENTIALS_FILE = "credentials.json"
MAX_REPLIES_PER_SESSION = 1
TYPING_SPEED_RANGE = (0.05, 0.2) # Seconds per character
WAIT_TIME_RANGE = (5, 15) # Seconds between actions
MANUAL_REVIEW = False# If True, bot waits for user Y/N before posting
SKIP_LOGIN = False # Set to True to skip login for post discovery testing
USE_PROXY = False # Keep False for now to build reputation on direct IP
RESET_SESSION = False # CRITICAL: Keep False to 'Warm Up' the browser profile
