import time
import random
import sqlite3
from playwright.sync_api import sync_playwright
from ai_replier import AIReplier
from gmail_verifier import GmailVerifier
import config

class AutomationBot:
    def __init__(self, db_path='bot_data.db'):
        self.db_path = db_path
        self.replier = AIReplier(api_key=config.CEREBRAS_API_KEY)
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                post_id TEXT UNIQUE,
                post_url TEXT,
                reply_content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def human_type(self, element, text):
        """Simulates human-like typing."""
        for char in text:
            element.type(char)
            time.sleep(random.uniform(0.05, 0.2))

    def random_wait(self, min_sec=5, max_sec=15):
        """Waits for a random duration."""
        time.sleep(random.uniform(min_sec, max_sec))

    def human_scroll(self, page):
        """Simulates human-like scrolling."""
        for _ in range(random.randint(2, 5)):
            page.mouse.wheel(0, random.randint(300, 700))
            time.sleep(random.uniform(1, 3))

    def has_replied(self, post_id):
        """Checks if a post has already been replied to."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM interactions WHERE post_id = ?', (post_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def log_interaction(self, platform, post_id, post_url, reply_content):
        """Logs a successful interaction."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO interactions (platform, post_id, post_url, reply_content)
                VALUES (?, ?, ?, ?)
            ''', (platform, post_id, post_url, reply_content))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        conn.close()

    def login_ea(self, page):
        """Handles the login process for EA Forums with robust navigation handling."""
        print("Attempting to login to EA...")
        try:
            # Click Sign In button
            sign_in_button = page.wait_for_selector('a:has-text("Sign In")', timeout=10000)
            if sign_in_button:
                sign_in_button.click()
                page.wait_for_load_state('networkidle')
                
                # Enter Email
                print(f"Entering email: {config.EA_EMAIL}")
                page.wait_for_selector('#email')
                page.fill('#email', config.EA_EMAIL)
                page.click('#logInBtn')
                
                # Enter Password
                print("Entering password...")
                page.wait_for_selector('#password')
                page.fill('#password', config.EA_PASSWORD)
                page.click('#logInBtn')
                
                # Handle 2FA (Verification Code)
                self.random_wait(3, 5)
                if "verification" in page.url.lower() or page.query_selector('#btnSendCode') or page.query_selector('#twoFactorCode'):
                    print("2FA/Verification detected...")
                    
                    # If "Send Code" button exists, click it
                    send_code_btn = page.query_selector('#btnSendCode')
                    if send_code_btn:
                        print("Clicking Send Code button...")
                        send_code_btn.click()
                        self.random_wait(5, 10)

                    print("Fetching code from Gmail...")
                    verifier = GmailVerifier(config.GMAIL_USER, config.GMAIL_PASS)
                    code = verifier.get_verification_code('noreply@ea.com')
                    
                    if code:
                        print(f"Entering 2FA code: {code}")
                        page.wait_for_selector('#twoFactorCode')
                        page.fill('#twoFactorCode', code)
                        page.click('#btnSubmit')
                        page.wait_for_load_state('networkidle')
                    else:
                        print("Error: Could not retrieve 2FA code from Gmail.")
                
                print("Login process completed. Waiting for redirection...")
                self.random_wait(5, 10)
            else:
                print("Sign In button not found. Already logged in?")
        except Exception as e:
            print(f"Login failed or already logged in: {e}")

    def run_platform_task(self, platform_url, platform_name):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) 
            context = browser.new_context()
            page = context.new_page()
            
            print(f"Navigating to {platform_name}...")
            page.goto(platform_url)
            self.random_wait(5, 10)

            if "ea.com" in platform_url:
                self.login_ea(page)
                
                # Ensure we are on the forum category page after login
                print(f"Navigating back to category: {platform_url}")
                page.goto(platform_url)
                self.random_wait(5, 10)
                
                self.handle_ea_forums(page)
            
            browser.close()

    def handle_ea_forums(self, page):
        print("Scanning EA Forums for new posts...")
        # Find post links - using a more specific selector for post titles
        posts = page.query_selector_all('a[href*="/t5/"]')
        
        replies_count = 0
        for post in posts:
            if replies_count >= config.MAX_REPLIES_PER_SESSION:
                print(f"Reached limit of {config.MAX_REPLIES_PER_SESSION} replies. Stopping.")
                break
            
            try:
                post_url = post.get_attribute('href')
                # Filter to ensure it's a discussion post, not a category link
                if not post_url or "/t5/" not in post_url or any(x in post_url.lower() for x in ["category", "bd-p", "ct-p"]):
                    continue
                
                post_id = post_url.split('/')[-1]
                if self.has_replied(post_id):
                    continue
                
                full_post_url = f"https://forums.ea.com{post_url}" if post_url.startswith('/') else post_url
                print(f"Opening post: {full_post_url}")
                page.goto(full_post_url)
                self.random_wait(5, 8)
                
                # Get post content
                content_element = page.query_selector('.lia-message-body-content')
                if not content_element:
                    continue
                
                post_content = content_element.inner_text()
                print("Generating AI reply...")
                ai_reply = self.replier.generate_reply(post_content)
                
                # Find and click Reply button
                reply_button = page.query_selector('a:has-text("Reply")')
                if reply_button:
                    reply_button.click()
                    self.random_wait(3, 5)
                    
                    # Find text area and type
                    editor = page.query_selector('.lia-form-type-text, #tinyMceEditor, .mce-content-body') 
                    if editor:
                        print("Typing reply...")
                        self.human_type(editor, ai_reply)
                        self.random_wait(2, 4)
                        
                        # Click Post/Submit
                        submit_button = page.query_selector('input[type="submit"], button:has-text("Post")')
                        if submit_button:
                            # submit_button.click() # Uncomment to actually post
                            print(f"SUCCESS: Reply prepared for post {post_id}")
                            self.log_interaction("EA Forums", post_id, post_url, ai_reply)
                            replies_count += 1
                            self.random_wait(10, 20)
                
                # Go back to the category page
                page.go_back()
                self.random_wait(3, 5)
            except Exception as e:
                print(f"Error processing post: {e}")
                continue

if __name__ == "__main__":
    bot = AutomationBot()
    bot.run_platform_task('https://forums.ea.com/category/ea-forums-en', 'EA Forums')
