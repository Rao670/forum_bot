import os
import json

# This file maps specific websites to specific Email accounts.
# If a website is NOT listed here, the bot will use the default email from config.py

# Default accounts
URL_ACCOUNTS = {
    # Glide Apps
    "community.glideapps.com": "kmmmij022@gmail.com",
    
    # Webflow
    "discourse.webflow.com": "c62994490@gmail.com",
    
    # Cursor
    "forum.cursor.com": "raoathar670@gmail.com",
    
    # Ansible
    "forum.ansible.com": "kmmmij022@gmail.com",
    
    # Arduino
    "forum.arduino.cc": "kevinsmith67011@gmail.com",
    
    # FreeCodeCamp
    "forum.freecodecamp.org": "raoathar670@gmail.com",
    
    # Modular
    "forum.modular.com": "kmmmij022@gmail.com",
    
    # Zoom
    "devforum.zoom.us": {"email":"raoabdullah4054@gmail.com",
    "password":"Sahibdad670"},

    # Unity
    "discussions.unity.com": "raoabdullah4054@gmail.com",
    
    # Bubble
    "https://forum.bubble.io/": "raoathar670@gmail.com",
    
    # Shop ware
    "https://forum.shopware.com/": "alexhale4054@gmail.com",
    
    "https://forum.gitlab.com/": "raoathar670@gmail.com",
    
    "https://forum.figma.com/": "raoathar670@gmail.com",        
    "https://forum.sketch.com/": "raoathar670@gmail.com",        
}

# Override with environment variable if available
url_accounts_env = os.environ.get("URL_ACCOUNTS_JSON")
if url_accounts_env:
    try:
        URL_ACCOUNTS.update(json.loads(url_accounts_env))
    except:
        pass
