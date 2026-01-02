import time
import random
import sqlite3
from playwright.sync_api import sync_playwright
from ai_replier import AIReplier
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

    def run_platform_task(self, platform_url, platform_name):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) # Headless=False to see the bot working
            context = browser.new_context()
            page = context.new_page()
            
            print(f"Navigating to {platform_name}...")
            page.goto(platform_url)
            self.random_wait(5, 10)

            # EA Forums specific logic
            if "ea.com" in platform_url:
                self.handle_ea_forums(page)
            
            browser.close()

    def handle_ea_forums(self, page):
        print("Scanning EA Forums for new posts...")
        # Find post links (this is a simplified selector, might need adjustment based on live site)
        posts = page.query_selector_all('a[href*="/t5/"]')
        
        replies_count = 0
        for post in posts:
            if replies_count >= config.MAX_REPLIES_PER_SESSION:
                print(f"Reached limit of {config.MAX_REPLIES_PER_SESSION} replies. Stopping.")
                break
            
            post_url = post.get_attribute('href')
            if not post_url or "/t5/" not in post_url:
                continue
            
            post_id = post_url.split('/')[-1]
            
            if self.has_replied(post_id):
                print(f"Already replied to post {post_id}. Skipping.")
                continue
            
            print(f"Opening post: {post_url}")
            page.goto(f"https://forums.ea.com{post_url}" if post_url.startswith('/') else post_url)
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
                editor = page.query_selector('.lia-form-type-text') # Adjust selector if needed
                if editor:
                    print("Typing reply...")
                    self.human_type(editor, ai_reply)
                    self.random_wait(2, 4)
                    
                    # Click Post/Submit
                    submit_button = page.query_selector('input[type="submit"]')
                    if submit_button:
                        # submit_button.click() # Uncomment this to actually post
                        print(f"SUCCESS: Reply prepared for post {post_id}")
                        self.log_interaction("EA Forums", post_id, post_url, ai_reply)
                        replies_count += 1
                        self.random_wait(10, 20)
            
            page.go_back()
            self.random_wait(3, 5)

if __name__ == "__main__":
    bot = AutomationBot()
    bot.run_platform_task('https://forums.ea.com/category/ea-forums-en', 'EA Forums')
