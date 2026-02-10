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

    # ================= DB =================
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

    def has_replied(self, post_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM interactions WHERE post_id = ?', (post_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def log_interaction(self, platform, post_id, post_url, reply_content):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO interactions (platform, post_id, post_url, reply_content)
                VALUES (?, ?, ?, ?)
            ''', (platform, post_id, post_url, reply_content))
            conn.commit()
            print(f"✓ Logged reply to DB for post: {post_id}")
        except sqlite3.IntegrityError:
            print(f"⚠ Post {post_id} already exists in DB")
        conn.close()

    # ================= Utilities =================
    def human_type(self, element, text):
        for char in text:
            element.type(char)
            time.sleep(random.uniform(*config.TYPING_SPEED_RANGE))

    def random_wait(self, min_sec=3, max_sec=7):
        time.sleep(random.uniform(min_sec, max_sec))

    # ================= Login =================
    def login_ea(self, page):
        print("🔐 Logging in...")
        try:
            self.random_wait(2, 4)
            if page.query_selector('a:has-text("Sign Out")') or page.query_selector('.lia-user-name'):
                print("✓ Already logged in")
                return True

            sign_in_btn = page.query_selector('a:has-text("Sign In")')
            if sign_in_btn:
                sign_in_btn.click()
                self.random_wait(2, 4)
                page.fill('#email', config.EA_EMAIL)
                page.click('#logInBtn')
                self.random_wait(2, 4)
                page.fill('#password', config.EA_PASSWORD)
                page.click('#logInBtn')
                self.random_wait(5, 8)
                print("✓ Login completed")
            return True
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

    # ================= Scroll & find random post =================
    def open_random_post_in_subcategory(self, page):
        print("🔍 Scrolling subcategory page to load posts...")
        posts = []
        attempts = 0
        max_attempts = 10

        while not posts and attempts < max_attempts:
            page.evaluate("window.scrollBy(0, window.innerHeight);")
            self.random_wait(1, 2)
            posts = page.query_selector_all('a[href*="/td-p/"], a[href*="/m-p/"], a[href*="/ba-p/"]')
            attempts += 1

        if not posts:
            print("⚠ No posts found in this subcategory")
            return None

        # Randomly select a post instead of the first one
        selected_post = random.choice(posts)
        post_url = selected_post.get_attribute('href')
        full_url = post_url if post_url.startswith('http') else f"https://forums.ea.com{post_url}"
        page.goto(full_url)
        self.random_wait(4, 7)
        print(f"✅ Opened post: {full_url}")
        return full_url

    # ================= Reply =================
    def reply_to_post(self, page, post_url, platform_name="EA Forums"):
        try:
            page.goto(post_url)
            self.random_wait(3, 6)

            # Find post content
            content_selectors = [
                '.lia-message-body-content',
                '.lia-message-body',
                'div[class*="message-body"]',
                '.lia-quilt-row-main .lia-message-body',
                'div[itemprop="text"]'
            ]
            content_element = None
            for sel in content_selectors:
                content_element = page.query_selector(sel)
                if content_element:
                    break
            if not content_element:
                print(f"⚠ Cannot find post content: {post_url}")
                return False

            post_content = content_element.inner_text()[:500]

            # Extract post ID
            post_id = None
            for pattern in ['/td-p/', '/m-p/', '/ba-p/']:
                if pattern in post_url:
                    post_id = post_url.split(pattern)[-1].split('?')[0].split('#')[0].split('/')[0]
                    break

            if not post_id:
                print(f"⏭ Cannot get post ID: {post_url}")
                return False

            if self.has_replied(post_id):
                print(f"⏭ Already replied to post: {post_id}")
                return False

            # AI Reply
            print("🤖 Generating AI reply...")
            ai_reply = self.replier.generate_reply(post_content)
            print(f"💬 AI Reply: {ai_reply[:200]}...")

            # Click reply button
            reply_btn = page.locator('a:has-text("Reply"), button:has-text("Reply")').first
            if not reply_btn:
                print("⚠ Reply button not found")
                return False
            reply_btn.click()
            self.random_wait(2, 4)

            # Find editor
            editor_selectors = [
                'textarea[name="body"]',
                'textarea[id*="body"]',
                'div[contenteditable="true"]',
                'iframe[title*="editor"]'
            ]
            editor = None
            for sel in editor_selectors:
                editor = page.query_selector(sel)
                if editor:
                    break
            if not editor:
                print("⚠ Editor not found")
                return False

            if 'iframe' in editor.get_attribute('outerHTML'):
                frame = page.frame(name=editor.get_attribute('name'))
                frame_body = frame.query_selector('body')
                frame_body.click()
                self.human_type(frame_body, ai_reply)
            else:
                editor.click()
                self.human_type(editor, ai_reply)

            # Submit
            submit_btn = page.locator('button:has-text("Post"), input[type="submit"]').first
            if submit_btn:
                submit_btn.click()
                self.random_wait(3, 5)
                print(f"✅ Reply submitted for post {post_id}")
                self.log_interaction(platform_name, post_id, post_url, ai_reply)
                return True
            else:
                print("⚠ Submit button not found")
                return False

        except Exception as e:
            print(f"❌ Error replying: {e}")
            return False

    # ================= Run Bot =================
    def run_platform_task(self, platform_url, platform_name="EA Forums"):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(platform_url)
            self.random_wait(5, 8)

            if not self.login_ea(page):
                print("❌ Login failed")
                browser.close()
                return

            # Community Selection
            print("🌍 Selecting a random community...")
            self.random_wait(2, 4)
            community_links = page.query_selector_all('a[href*="/forums/"], a[href*="/games/"], a[href*="/category/"]')
            
            # Filter out invalid links
            valid_community_links = []
            for link in community_links:
                href = link.get_attribute('href')
                if href and ('/forums/' in href or '/games/' in href or '/category/' in href):
                    valid_community_links.append(link)
            
            if not valid_community_links:
                print("⚠ No community links found on the main page. Trying alternative selectors...")
                # Try alternative selectors
                community_links = page.query_selector_all('a[class*="community"], a[class*="forum"], a[href*="/t5/"]')
                valid_community_links = [l for l in community_links if l.get_attribute('href')]
            
            if not valid_community_links:
                print("⚠ No community links found. Proceeding with current page...")
                community_url = platform_url
            else:
                random_community_link = random.choice(valid_community_links)
                community_url = random_community_link.get_attribute('href')
                if not community_url.startswith('http'):
                    community_url = f"https://forums.ea.com{community_url}"
                
                page.goto(community_url)
                self.random_wait(5, 8)
                print(f"✅ Entered community: {community_url}")

            # Collect subcategory / discussion links
            print("📂 Finding categories...")
            self.random_wait(2, 4)
            sub_links = page.query_selector_all('a[href*="/category/"], a[href*="/discussions/"], a[href*="/t5/"]')
            sub_urls = []
            for l in sub_links:
                href = l.get_attribute('href')
                if href:
                    full_url = href if href.startswith('http') else f"https://forums.ea.com{href}"
                    # Avoid duplicates
                    if full_url not in sub_urls:
                        sub_urls.append(full_url)
            
            if not sub_urls:
                print("⚠ No subcategories/discussions found in this community.")
                browser.close()
                return

            print(f"🔍 Found {len(sub_urls)} subcategories/discussions in the selected community.")

            # Visit a random subcategory
            random_subcategory_url = random.choice(sub_urls)
            page.goto(random_subcategory_url)
            self.random_wait(3, 6)
            print(f"✅ Entered subcategory: {random_subcategory_url}")

            # Find all posts in the category
            print("📝 Looking for posts...")
            self.random_wait(2, 4)
            all_posts = page.query_selector_all('a[href*="/td-p/"], a[href*="/m-p/"], a[href*="/ba-p/"]')
            
            # Scroll to load more posts if needed
            if not all_posts:
                print("Scrolling to load more posts...")
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, window.innerHeight);")
                    self.random_wait(1, 2)
                    all_posts = page.query_selector_all('a[href*="/td-p/"], a[href*="/m-p/"], a[href*="/ba-p/"]')
                    if all_posts:
                        break

            if not all_posts:
                print("⚠ No posts found in this category.")
                browser.close()
                return

            print(f"📋 Found {len(all_posts)} posts in this category.")

            # Shuffle posts to get random selection
            random.shuffle(all_posts)

            # Reply to only 1 unique post
            replied = False
            for post_element in all_posts:
                if replied:
                    break

                post_url = post_element.get_attribute('href')
                if not post_url:
                    continue

                full_post_url = post_url if post_url.startswith('http') else f"https://forums.ea.com{post_url}"
                
                # Extract post ID to check if already replied
                post_id = None
                for pattern in ['/td-p/', '/m-p/', '/ba-p/']:
                    if pattern in full_post_url:
                        post_id = full_post_url.split(pattern)[-1].split('?')[0].split('#')[0].split('/')[0]
                        break
                
                if post_id and not self.has_replied(post_id):
                    print(f"🎯 Attempting to reply to post: {post_id}")
                    if self.reply_to_post(page, full_post_url, platform_name):
                        replied = True
                        print(f"✅ Successfully replied to 1 post. Task completed!")
                        break
                else:
                    if post_id:
                        print(f"⏭ Skipping post (already replied): {post_id}")
                    else:
                        print(f"⏭ Skipping post (invalid ID): {full_post_url}")

                self.random_wait(2, 4)

            if not replied:
                print("⚠ Could not find any unique post to reply to in this category.")

            browser.close()

