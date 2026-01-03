import time
import random
import re
import sqlite3
from datetime import datetime
from playwright.sync_api import sync_playwright
from ai_replier import AIReplier
import config

class HuggingFaceBot:
    def __init__(self, db_path='bot_data.db'):
        self.db_path = db_path
        self.replier = AIReplier(api_key=config.CEREBRAS_API_KEY)
        self.reply_history_file = 'bubble_reply_history.txt'
        self._init_db()

    # ================= DB =================
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Use same interactions table, but we'll track platform
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
        cursor.execute('SELECT 1 FROM interactions WHERE post_id = ? AND platform = ?', 
                      (post_id, 'Bubble.io Forums'))
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
            
            # Save to text file
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.reply_history_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {platform}\n")
                f.write(f"Post ID: {post_id}\n")
                f.write(f"URL: {post_url}\n")
                f.write(f"Reply: {reply_content[:200]}...\n")
                f.write("-" * 80 + "\n\n")
            print(f"✓ Saved reply history to {self.reply_history_file}")
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

    def extract_post_id(self, url):
        """Extract post ID from HuggingFace forum URL"""
        if not url:
            return None
        
        # HuggingFace URLs format: /t/topic-title/12345
        match = re.search(r'/t/[^/]+/(\d+)', url)
        if match:
            return match.group(1)
        
        # Alternative format
        match = re.search(r'/(\d+)(?:\?|$)', url)
        if match:
            return match.group(1)
        
        return None

    # ================= Login =================
    def login_huggingface(self, page, platform_url="https://forum.bubble.io/"):
        print("🔐 Logging in...")
        try:
            self.random_wait(2, 4)
            
            # Check if already logged in - better verification
            logged_in_indicators = [
                '.current-user',
                '[data-user-card]',
                '.user-menu',
                '.header-dropdown-toggle',
                '[class*="user-menu"]',
                '[class*="current-user"]'
            ]
            
            is_logged_in = False
            for indicator in logged_in_indicators:
                if page.query_selector(indicator):
                    is_logged_in = True
                    break
            
            # Also check if login button is NOT visible (means logged in)
            login_btn_visible = False
            for sel in ['a[href*="/login"]', 'button:has-text("Log in")', 'a:has-text("Log in")']:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        login_btn_visible = True
                        break
                except:
                    pass
            
            if is_logged_in and not login_btn_visible:
                print("✓ Already logged in")
                return True
            elif not is_logged_in and login_btn_visible:
                print("📍 Not logged in, proceeding with login...")
            else:
                print("📍 Login status unclear, attempting login...")

            # Find and click login button
            login_selectors = [
                'a[href*="/login"]',
                'button:has-text("Log in")',
                'a:has-text("Log in")',
                'a:has-text("Login")',
                '.login-button',
                '[data-login-button]'
            ]
            
            login_btn = None
            for sel in login_selectors:
                try:
                    btn = page.query_selector(sel)
                    if btn:
                        login_btn = btn
                        break
                except:
                    continue
            
            if not login_btn:
                print("⚠ Login button not found")
                return False
            
            login_btn.click()
            self.random_wait(5, 8)  # Wait after clicking login

            # After clicking login, check if there's another login option/button on the login page
            # Sometimes Discourse shows a login modal/page with another login button
            secondary_login_selectors = [
                'button:has-text("Log in")',
                'a:has-text("Log in")',
                'button:has-text("Login")',
                'a:has-text("Login")',
                '.login-button',
                '[data-login-button]',
                'button.create',
                'a.create',
                'a[href*="/login"]',
                'button[class*="login"]',
                'a[class*="login"]'
            ]
            
            # Try to find and click secondary login option if exists (multiple attempts)
            for attempt in range(3):
                self.random_wait(2, 3)  # Wait between attempts
                for sel in secondary_login_selectors:
                    try:
                        secondary_btn = page.query_selector(sel)
                        if secondary_btn:
                            # Check if button is visible
                            is_visible = secondary_btn.is_visible() if hasattr(secondary_btn, 'is_visible') else True
                            if is_visible:
                                print(f"📍 Found secondary login option (attempt {attempt+1}), clicking...")
                                secondary_btn.click()
                                self.random_wait(2, 4)  # Wait after clicking
                                break
                    except:
                        continue
                else:
                    continue
                break

            # Fill credentials - try multiple selectors (avoid signup fields)
            email_selectors = [
                'input[name="login"]',  # Discourse uses "login" for email
                'input[name="email"]',
                'input[type="email"]:not([id*="signup"]):not([id*="Signup"])',  # Exclude signup fields
                'input[id*="email"]:not([id*="signup"]):not([id*="Signup"])',
                'input[placeholder*="email" i]:not([id*="signup"])',
                '#login-account-name',  # Discourse login field
                '#email:not([id*="signup"])'
            ]
            
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]:not([id*="signup"]):not([id*="Signup"])',  # Exclude signup fields
                'input[id*="password"]:not([id*="signup"]):not([id*="Signup"])',
                'input[placeholder*="password" i]:not([id*="signup"])',
                '#login-account-password',  # Discourse password field
                '#password:not([id*="signup"])'
            ]
            
            # Wait for login form to appear
            print("⏳ Waiting for login form...")
            self.random_wait(5, 8)
            
            # Fill email - try to find visible login field (not signup)
            email_filled = False
            for sel in email_selectors:
                try:
                    # Try to find all matching elements
                    all_email_fields = page.query_selector_all(sel)
                    for email_field in all_email_fields:
                        try:
                            # Check if field is visible and not in signup form
                            field_id = email_field.get_attribute('id') or ''
                            field_name = email_field.get_attribute('name') or ''
                            
                            # Skip signup fields
                            if 'signup' in field_id.lower() or 'signup' in field_name.lower():
                                continue
                            
                            # Check visibility using JavaScript
                            is_visible = page.evaluate('''el => {
                                const style = window.getComputedStyle(el);
                                return style.display !== 'none' && 
                                       style.visibility !== 'hidden' && 
                                       style.opacity !== '0' &&
                                       el.offsetWidth > 0 && 
                                       el.offsetHeight > 0;
                            }''', email_field)
                            
                            if is_visible:
                                email_field.fill(config.EA_EMAIL)
                                email_filled = True
                                print(f"✓ Email filled using selector: {sel}")
                                break
                        except Exception as e:
                            continue
                    
                    if email_filled:
                        break
                except Exception as e:
                    print(f"⚠ Email selector {sel} failed: {e}")
                    continue
            
            if not email_filled:
                print("⚠ Email field not found - trying alternative approach...")
                # Try waiting more and retry with all input fields
                self.random_wait(3, 5)
                
                # Try to find any visible email input (excluding signup)
                all_inputs = page.query_selector_all('input[type="email"], input[name="login"], input[name="email"]')
                for input_field in all_inputs:
                    try:
                        input_id = input_field.get_attribute('id') or ''
                        input_name = input_field.get_attribute('name') or ''
                        # Skip signup fields
                        if 'signup' not in input_id.lower() and 'signup' not in input_name.lower():
                            # Try to fill
                            input_field.fill(config.EA_EMAIL)
                            email_filled = True
                            print("✓ Email filled (alternative approach)")
                            break
                    except:
                        continue
                
                if not email_filled:
                    print("❌ Email field not found after retry")
                    return False
            
            self.random_wait(3, 5)  # Wait after filling email
            
            # Fill password
            password_filled = False
            for sel in password_selectors:
                try:
                    # Use locator instead for better waiting
                    password_locator = page.locator(sel).first
                    if password_locator.count() > 0:
                        password_locator.wait_for(state="visible", timeout=15000)
                        password_locator.fill(config.EA_PASSWORD)  # Using same config
                        password_filled = True
                        print("✓ Password filled")
                        break
                except Exception as e:
                    print(f"⚠ Password selector {sel} failed: {e}")
                    continue
            
            if not password_filled:
                print("⚠ Password field not found - trying alternative approach...")
                self.random_wait(3, 5)
                for sel in password_selectors:
                    try:
                        password_field = page.query_selector(sel)
                        if password_field:
                            password_field.fill(config.EA_PASSWORD)
                            password_filled = True
                            print("✓ Password filled (retry)")
                            break
                    except:
                        continue
                
                if not password_filled:
                    print("❌ Password field not found after retry")
                    return False
            
            self.random_wait(3, 5)  # Wait after filling password
            
            # Click submit/login button
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Log in")',
                'button:has-text("Sign in")',
                'button:has-text("Login")',
                '.login-button',
                '[type="submit"]'
            ]
            
            for sel in submit_selectors:
                try:
                    submit_btn = page.query_selector(sel)
                    if submit_btn:
                        submit_btn.click()
                        break
                except:
                    continue
            
            self.random_wait(8, 12)  # Wait after submitting login
            
            # Check current URL - if redirected away from login page, login likely succeeded
            current_url = page.url
            print(f"📍 Current URL after login: {current_url}")
            
            # If we're not on login page anymore, login likely succeeded
            if 'login' not in current_url.lower():
                print("✓ Login appears successful (redirected from login page)")
                # Go back to the original platform URL (not hardcoded)
                print(f"📍 Navigating back to original forum page: {platform_url}")
                try:
                    page.goto(platform_url, wait_until="domcontentloaded", timeout=60000)
                    self.random_wait(5, 8)
                except:
                    pass
                return True
            
            # Verify login - better verification
            login_success = False
            
            # Check for logged in indicators
            logged_in_indicators = [
                '.current-user',
                '[data-user-card]',
                '.user-menu',
                '.header-dropdown-toggle',
                '[class*="user-menu"]'
            ]
            
            for indicator in logged_in_indicators:
                if page.query_selector(indicator):
                    login_success = True
                    break
            
            # Also check if login button is gone
            if not login_success:
                login_btn_found = False
                for sel in ['a[href*="/login"]', 'button:has-text("Log in")', 'a:has-text("Log in")']:
                    try:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            login_btn_found = True
                            break
                    except:
                        pass
                
                if not login_btn_found:
                    # Login button not visible, might be logged in
                    login_success = True
            
            if login_success:
                print("✓ Login completed")
                # Always go to main forum page after successful login (use platform_url)
                current_url_after = page.url
                # Extract base URL from platform_url
                from urllib.parse import urlparse
                parsed = urlparse(platform_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}/"
                
                if current_url_after != base_url and parsed.netloc not in current_url_after:
                    print(f"📍 Navigating to main forum page: {base_url}")
                    try:
                        page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                        self.random_wait(5, 8)
                        print("✓ Reached main forum page")
                    except Exception as e:
                        print(f"⚠ Navigation error: {e}")
                else:
                    print("✓ Already on main forum page")
                return True
            else:
                print("⚠ Login verification failed - please check credentials")
                return False
                
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

    # ================= Reply =================
    def reply_to_post(self, page, post_url, platform_name="Bubble.io Forums"):
        try:
            page.goto(post_url)
            self.random_wait(3, 6)

            # Extract post ID
            post_id = self.extract_post_id(post_url)
            if not post_id:
                print(f"⏭ Cannot get post ID: {post_url}")
                return False

            if self.has_replied(post_id):
                print(f"⏭ Already replied to post: {post_id}")
                return False

            # Check if post is solved/closed - check for "Solved by" text
            is_solved = False
            
            # Check page content for "Solved by" text (common in Discourse forums)
            try:
                page_text = page.inner_text('body').lower()
                if 'solved by' in page_text:
                    # Find the solved indicator element
                    solved_text_elements = page.query_selector_all('*')
                    for elem in solved_text_elements:
                        try:
                            text = elem.inner_text().lower()
                            if 'solved by' in text and len(text) < 100:  # Short text likely to be the indicator
                                is_solved = True
                                print(f"📍 Post is marked as Solved (found: 'Solved by' text)")
                                break
                        except:
                            continue
            except:
                pass
            
            # Also check in specific solved indicator areas
            if not is_solved:
                solved_indicators = [
                    '.topic-status-info[title*="Solved" i]',
                    '.topic-status-info[title*="solved" i]',
                    '[class*="topic-status"] [class*="solved"]',
                    'span.solved',
                    '[data-topic-status="solved"]',
                    '.solved-badge',
                    '.solved-indicator',
                    '[class*="solved-by"]'
                ]
                
                for sel in solved_indicators:
                    try:
                        solved_element = page.query_selector(sel)
                        if solved_element:
                            # Make sure it's visible and actually says solved
                            if solved_element.is_visible():
                                text = solved_element.inner_text().lower()
                                title = solved_element.get_attribute('title') or ''
                                if 'solved' in text.lower() or 'solved' in title.lower():
                                    is_solved = True
                                    print(f"📍 Post is marked as Solved (found: {text or title})")
                                    break
                    except:
                        continue
            
            # Only skip if we're 100% sure it's solved
            if is_solved:
                print(f"⏭ Skipping post - it's marked as 'Solved'")
                return False

            # Find post content
            content_selectors = [
                '.post-body',
                '.cooked',
                '[itemprop="text"]',
                '.topic-body',
                '.post-content',
                'div[class*="post-body"]'
            ]
            
            content_element = None
            for sel in content_selectors:
                try:
                    content_element = page.query_selector(sel)
                    if content_element:
                        break
                except:
                    continue
            
            if not content_element:
                print(f"⚠ Cannot find post content: {post_url}")
                return False

            post_content = content_element.inner_text()[:500]

            # AI Reply
            print("🤖 Generating AI reply...")
            ai_reply = self.replier.generate_reply(post_content)
            print(f"💬 AI Reply: {ai_reply[:200]}...")

            # Find and click reply button
            self.random_wait(2, 3)
            reply_selectors = [
                'button.create',
                'button:has-text("Reply")',
                'a:has-text("Reply")',
                '.reply-button',
                '[data-action="reply"]',
                'button[title*="Reply" i]'
            ]
            
            reply_btn = None
            for sel in reply_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.count() > 0:
                        reply_btn = btn
                        break
                except:
                    continue
            
            if not reply_btn or reply_btn.count() == 0:
                print("⏭ Reply button not found - skipping this post")
                return False
            
            # Wait for button to be enabled
            try:
                reply_btn.wait_for(state="visible", timeout=10000)
                is_disabled = None
                try:
                    is_disabled = reply_btn.get_attribute('disabled')
                except:
                    try:
                        btn_element = reply_btn.element_handle()
                        if btn_element:
                            is_disabled = page.evaluate('el => el.disabled', btn_element)
                    except:
                        pass
                
                if is_disabled:
                    print("⏳ Reply button is disabled, waiting...")
                    for _ in range(20):
                        self.random_wait(0.5, 1)
                        try:
                            is_disabled = reply_btn.get_attribute('disabled')
                            if not is_disabled:
                                break
                        except:
                            pass
                
                reply_btn.click(timeout=5000)
                self.random_wait(2, 4)
            except Exception as e:
                print(f"⏭ Error clicking reply button: {e} - skipping this post")
                return False

            # Find editor
            self.random_wait(1, 2)
            editor_selectors = [
                '.d-editor-input',
                'textarea.d-editor-input',
                'textarea[placeholder*="reply" i]',
                'div[contenteditable="true"]',
                'textarea[name="raw"]',
                'textarea[id*="reply"]'
            ]
            
            editor = None
            for sel in editor_selectors:
                try:
                    editor_element = page.query_selector(sel)
                    if editor_element:
                        editor = editor_element
                        break
                except:
                    continue
            
            if not editor:
                print("⏭ Editor not found - skipping this post")
                return False

            # Type reply
            try:
                editor.click()
                self.random_wait(0.5, 1)
                self.human_type(editor, ai_reply)
            except Exception as e:
                print(f"⏭ Error typing reply: {e} - skipping this post")
                return False

            # Submit
            self.random_wait(1, 2)
            submit_selectors = [
                'button.create',
                'button:has-text("Post Reply")',
                'button:has-text("Reply")',
                'button[type="submit"]',
                '.submit-panel button',
                'button.create:has-text("Reply")'
            ]
            
            submit_btn = None
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.count() > 0:
                        try:
                            btn.wait_for(state="visible", timeout=2000)
                            submit_btn = btn
                            break
                        except:
                            continue
                except:
                    continue
            
            if submit_btn and submit_btn.count() > 0:
                try:
                    # Wait for button to be enabled
                    is_disabled = None
                    try:
                        is_disabled = submit_btn.get_attribute('disabled')
                    except:
                        try:
                            btn_element = submit_btn.element_handle()
                            if btn_element:
                                is_disabled = page.evaluate('el => el.disabled', btn_element)
                        except:
                            pass
                    
                    if is_disabled:
                        for _ in range(10):
                            self.random_wait(0.5, 1)
                            try:
                                is_disabled = submit_btn.get_attribute('disabled')
                                if not is_disabled:
                                    break
                            except:
                                pass
                    
                    submit_btn.click(timeout=10000)
                    self.random_wait(5, 8)  # More wait after submit
                    
                    # Verify reply was submitted - check if editor is gone or reply appeared
                    try:
                        # Wait a bit and check if we're still on the page
                        self.random_wait(2, 3)
                        # Check if editor disappeared (means reply was submitted)
                        editor_still_there = page.query_selector('.d-editor-input')
                        if not editor_still_there:
                            print(f"✅ Reply submitted for post {post_id}")
                            self.log_interaction(platform_name, post_id, post_url, ai_reply)
                            return True
                        else:
                            print("⚠ Editor still visible, reply might not have been submitted")
                            # Try clicking submit again
                            try:
                                submit_btn.click(timeout=5000)
                                self.random_wait(3, 5)
                                print(f"✅ Reply submitted for post {post_id} (retry)")
                                self.log_interaction(platform_name, post_id, post_url, ai_reply)
                                return True
                            except:
                                pass
                    except:
                        pass
                    
                    # If we reach here, assume it worked
                    print(f"✅ Reply submitted for post {post_id}")
                    self.log_interaction(platform_name, post_id, post_url, ai_reply)
                    return True
                except Exception as submit_error:
                    print(f"⏭ Could not submit reply: {submit_error} - skipping this post")
                    return False
            else:
                print("⏭ Submit button not found - skipping this post")
                return False

        except Exception as e:
            print(f"⏭ Error replying to post: {e} - skipping this post")
            import traceback
            traceback.print_exc()
            return False

    # ================= Run Bot =================
    def run_huggingface_task(self, platform_url="https://forum.bubble.io/"):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            
            # Increase timeout and wait for page to load properly
            print("🌐 Loading forum page...")
            try:
                page.goto(platform_url, wait_until="domcontentloaded", timeout=30000)
                # Check if page actually loaded
                self.random_wait(3, 5)
                # If page seems stuck, reload
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    print("⚠ Page loading slowly, reloading...")
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    self.random_wait(3, 5)
            except Exception as e:
                print(f"⚠ Page load timeout, trying reload... {e}")
                try:
                    page.reload(wait_until="domcontentloaded", timeout=30000)
                    self.random_wait(3, 5)
                except:
                    print("⚠ Reload also failed, continuing anyway...")
                    self.random_wait(2, 3)

            # Login
            if not self.login_huggingface(page, platform_url):
                print("❌ Login failed")
                browser.close()
                return

            # Go back to main page after login (important - login ke baad redirect ho sakta hai kahi aur)
            current_url = page.url
            if platform_url not in current_url:
                print(f"📍 Redirected to: {current_url}, going back to main page...")
                try:
                    page.goto(platform_url, wait_until="domcontentloaded", timeout=60000)
                    self.random_wait(2, 3)  # Wait after navigation
                except Exception as e:
                    print(f"⚠ Navigation timeout, but continuing... {e}")
                    self.random_wait(5, 8)
            else:
                print("✓ Already on main page")
                self.random_wait(3, 5)

            # Scroll to load posts
            print("📝 Looking for posts...")
            self.random_wait(5, 8)  # Wait before scrolling
            for _ in range(3):
                page.evaluate("window.scrollBy(0, window.innerHeight);")
                self.random_wait(3, 5)  # Wait between scrolls

            # Find posts - HuggingFace uses Discourse format
            post_selectors = [
                'a.topic-title',
                'a[href*="/t/"]',
                '.topic-list-item a',
                'tr.topic-list-item a'
            ]
            
            all_posts = []
            for sel in post_selectors:
                try:
                    posts = page.query_selector_all(sel)
                    for post in posts:
                        href = post.get_attribute('href')
                        if href and '/t/' in href and self.extract_post_id(href):
                            if post not in all_posts:
                                all_posts.append(post)
                except:
                    continue

            if not all_posts:
                print("⚠ No posts found")
                browser.close()
                return

            print(f"📋 Found {len(all_posts)} posts")

            # Shuffle and try to reply to one
            random.shuffle(all_posts)
            replied = False

            # First, collect all post URLs before navigation (to avoid stale element references)
            post_urls = []
            for post_element in all_posts:
                try:
                    post_url = post_element.get_attribute('href')
                    if post_url:
                        # Make full URL
                        if post_url.startswith('/'):
                            full_post_url = f"https://forum.bubble.io{post_url}"
                        elif post_url.startswith('http'):
                            full_post_url = post_url
                        else:
                            full_post_url = f"https://forum.bubble.io/{post_url}"
                        
                        post_id = self.extract_post_id(full_post_url)
                        if post_id:
                            post_urls.append((post_id, full_post_url))
                except Exception as e:
                    print(f"⚠ Error getting post URL: {e}")
                    continue

            # Shuffle URLs
            random.shuffle(post_urls)
            
            # Now try to reply to posts
            replied = False
            for post_id, full_post_url in post_urls:
                if replied:
                    break
                
                if not self.has_replied(post_id):
                    print(f"🎯 Attempting to reply to post: {post_id}")
                    if self.reply_to_post(page, full_post_url, "Bubble.io Forums"):
                        replied = True
                        print(f"✅ Successfully replied to 1 post. Task completed!")
                        break
                else:
                    print(f"⏭ Skipping post (already replied): {post_id}")

                self.random_wait(2, 4)

            if not replied:
                print("⚠ Could not find any unique post to reply to")

            browser.close()

