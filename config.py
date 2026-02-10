# Configuration file for the Automation Bot

# Gmail Credentials
# Note: Use an "App Password" instead of your regular password if you have 2FA enabled.
EA_EMAIL = "raoathar670@gmail.com"
EA_PASSWORD = "Sahibdad670!"

# API Keys
# CEREBRAS_API_KEY = "csk-fthmtp5jrkfkjhfmvdtyjvkwx5jc95vnn8d5eenk42kkyxcw"
# Put multiple keys in this list: ["key1", "key2", "key3"]
GEMINI_API_KEYS = [
    "AIzaSyDi2D0hA3pZ8b4hIAEiRi8RsVxAu8gR6_E",
    "AIzaSyAQD9uIqK8KYmNcd5j9cJc6cSPYK1_smu8", 
    "AIzaSyBBjnEpVzo9VH7nfFHOFsW-0KsmUmqYdhs",
    "AIzaSyCxh_ANVqQVOAaK6LpVGshV53ungwIhK9E",
    "AIzaSyAzWAWbkqHSY5IteOS-G83gCL6r7TG7tIs",
    

    # "ADD_MORE_KEYS_HERE"
]

# Bot Settings
USE_GEMINI = True   # Set to True to use Gemini
USE_CEREBRAS = False# Set to True to use Cerebras (Fallback when Gemini fails)
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/1SjFn694SBeLi0G_Sjlks4WyKjBg601gek7ohXLYXNWI/edit"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
MAX_REPLIES_PER_SESSION = 1
TYPING_SPEED_RANGE = (0.05, 0.2) # Seconds per character
WAIT_TIME_RANGE = (5, 15) # Seconds between actions
MANUAL_REVIEW = False# If True, bot waits for user Y/N before posting
SKIP_LOGIN = False # Set to True to skip login for post discovery testing
USE_PROXY = False # Keep False for now to build reputation on direct IP
RESET_SESSION = False # CRITICAL: Keep False to 'Warm Up' the browser profile