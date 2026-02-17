import time
import urllib.request
import random
import re
import sqlite3
import os
import shutil
from datetime import datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from ai_replier import AIReplier
from proxy_manager import ProxyManager
import config
import accounts_config
import gspread
from oauth2client.service_account import ServiceAccountCredentials

class HuggingFaceBot:
    def __init__(self, db_path='bot_data.db'):
        self.db_path = db_path
        self.replier = AIReplier(api_key=getattr(config, 'CEREBRAS_API_KEY', None))
        self.reply_history_file = 'bubble_reply_history.txt'
        self.bot_aliases = ['Rao_Athar', 'KernelCoder', 'RaoAthar', 'Rao_Athar Account', 'pixelpioneer', 'PixelPioneer23', 'Peterson23']
        self.gsheet = None
        self._init_gsheets()
        self._init_db()
        # Track pacing across threads
        self.global_last_reply_time = 0

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                post_id TEXT,
                post_url TEXT,
                reply_content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Check if we need to remove UNIQUE constraint from an existing DB
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_post_id ON interactions(post_id)")
        except: pass
        
        conn.commit()
        conn.close()

    def _init_gsheets(self):
        cred_file = getattr(config, 'GOOGLE_CREDENTIALS_FILE', 'credentials.json')
        sheet_url = getattr(config, 'GOOGLE_SHEET_URL', '')
        
        if not os.path.exists(cred_file):
            print(f" [Info] {cred_file} not found. Google Sheet logging disabled.")
            return

        if not sheet_url:
            print(" [Info] GOOGLE_SHEET_URL not set. Google Sheet logging disabled.")
            return

        # Try to connect with retries (to handle transient DNS/Network issues)
        for attempt in range(3):
            try:
                scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
                creds = ServiceAccountCredentials.from_json_keyfile_name(cred_file, scope)
                client = gspread.authorize(creds)
                self.gsheet = client.open_by_url(sheet_url).sheet1
                
                # Only set headers if Row 1 is empty (respect user's manual setup)
                try:
                    first_row = self.gsheet.row_values(1)
                    if not first_row or not any(first_row):
                        # Row 1 is empty, set professional headers
                        headers = ["TIMESTAMP", "DATE", "PLATFORM", "TOPIC LINK", "BOT REPLY", "STATUS / ID"]
                        self.gsheet.update('A1:F1', [headers])
                        print(" [Setup] Headers set at A1:F1.")
                    else:
                        print(" [Info] Headers already exist. Skipping header setup.")
                except Exception as e:
                    print(f" [Warning] Could not check/set headers: {e}")
                
                print(" [Success] Connected to Google Sheet!")
                return # Success!
            except Exception as e:
                if attempt < 2:
                    print(f" [Retry] Google Sheet connection failed (Attempt {attempt+1}/3). Retrying in 5s...")
                    time.sleep(5)
                else:
                    print(f" [Error] Failed to connect to Google Sheet after 3 attempts: {e}")

    def has_replied(self, post_id, platform):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM interactions WHERE post_id = ? AND platform = ?', (post_id, platform))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def log_interaction(self, platform, post_id, post_url, reply_content):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO interactions (platform, post_id, post_url, reply_content, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (platform, post_id, post_url, reply_content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        except sqlite3.IntegrityError:
            # This is expected for follow-up replies since post_id is UNIQUE
            # We skip the DB insert but continue with other logging methods
            pass
        except Exception as e:
            print(f" [Error] Local database logging failed: {e}")
        
        # Ensure connection is closed even if commit fails
        try: conn.close()
        except: pass
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Existing Human-Readable Log
        with open(self.reply_history_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {platform}\n")
            f.write(f"Post ID: {post_id}\n")
            f.write(f"URL: {post_url}\n")
            f.write(f"Reply: {reply_content[:200]}...\n")
            f.write("-" * 50 + "\n")
        
        # 2. Google Sheets Compatible Log (TSV)
        # Columns: DATE | (Blank) | PLATFORM URL | REPLY URL | (Blank) | REPLY | Post ID
        # Note: 'post_url' serves as Reply URL here. Platform URL is just the base domain.
        platform_base = platform.split('/t/')[0] if '/t/' in platform else platform
        clean_reply = reply_content.replace('\n', ' ').replace('\t', ' ')
        tsv_line = f"{timestamp}\t\t{platform_base}\t{post_url}\t\t{clean_reply}\t{post_id}\n"
        
        with open('gsheet_logs.tsv', 'a', encoding='utf-8') as f:
            f.write(tsv_line)

        # 3. Direct Google Sheet Update
        if self.gsheet:
            # Retry loop for Google Sheets (handles API quota/timeout)
            for sheet_attempt in range(3):
                try:
                    # Get current headers from Row 1
                    try:
                        headers_row = self.gsheet.row_values(1)
                    except:
                        headers_row = []
                    
                    if not headers_row:
                        break # No headers, can't map

                    # Prepare data dictionary
                    dt_obj = datetime.now()
                    time_str = dt_obj.strftime("%H:%M:%S")
                    date_str = dt_obj.strftime("%Y-%m-%d") # Use current date

                    data_map = {
                        'TIMESTAMP': f"{date_str} {time_str}",
                        'DATE': date_str,
                        'PLATFORM': platform_base,
                        'TOPIC LINK': post_url,
                        'BOT REPLY': clean_reply,
                        'STATUS / ID': str(post_id)
                    }

                    # Construct the row based on headers
                    row_values = [''] * len(headers_row)
                    found_mapping = False
                    for i, header in enumerate(headers_row):
                        if not header: continue
                        header_upper = header.strip().upper()
                        if 'TIMESTAMP' in header_upper:
                            row_values[i] = data_map['TIMESTAMP']
                            found_mapping = True
                        elif 'DATE' in header_upper:
                            row_values[i] = data_map['DATE']
                            found_mapping = True
                        elif 'PLATFORM' in header_upper:
                            row_values[i] = data_map['PLATFORM']
                            found_mapping = True
                        elif 'TOPIC LINK' in header_upper or 'URL' in header_upper:
                            row_values[i] = data_map['TOPIC LINK']
                            found_mapping = True
                        elif 'BOT REPLY' in header_upper or 'REPLY' in header_upper:
                            row_values[i] = data_map['BOT REPLY']
                            found_mapping = True
                        elif 'STATUS' in header_upper or 'ID' in header_upper:
                            row_values[i] = data_map['STATUS / ID']
                            found_mapping = True

                    if not found_mapping:
                        row_values = [data_map['TIMESTAMP'], data_map['DATE'], data_map['PLATFORM'], data_map['TOPIC LINK'], data_map['BOT REPLY'], data_map['STATUS / ID']]

                    # Find next row
                    try:
                        col_a_values = self.gsheet.col_values(1)
                        filled_rows = [v for v in col_a_values if v.strip()]
                        next_row = len(filled_rows) + 1
                        if next_row <= 1: next_row = 2
                    except:
                        all_data = self.gsheet.get_all_values()
                        next_row = max(2, len(all_data) + 1)
                    
                    # Update the row
                    def col_idx_to_letter(idx):
                        return chr(65 + idx) if idx < 26 else 'Z'
                    
                    last_letter = col_idx_to_letter(len(row_values) - 1)
                    range_notation = f'A{next_row}:{last_letter}{next_row}'
                    
                    self.gsheet.update(range_notation, [row_values])
                    print(f" [Success] Logged to Google Sheet (Row {next_row}).")
                    break # Success!
                except Exception as e:
                    print(f" [Retry {sheet_attempt + 1}/3] Google Sheet update failed: {e}")
                    time.sleep(2)
                    if sheet_attempt == 2:
                        print(" [X] Could not log to Google Sheets after 3 attempts.")

    def human_type(self, element, text):
        try:
            for char in text:
                element.type(char)
                time.sleep(random.uniform(0.01, 0.05)) # Fast but variable
        except Exception as e:
            print(f" [Warning] Typing interrupted (likely element detached): {e}")

    def smart_scroll(self, page, max_attempts=15, wait_time=2):
        """
        Smartly scrolls to the bottom of the page, handling lazy-loaded content.
        Continues until the scroll height stops changing.
        """
        print(" [SmartScroll] Reaching for the true bottom of the thread...")
        last_height = page.evaluate("document.body.scrollHeight")
        for attempt in range(max_attempts):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.random_wait(wait_time, wait_time + 1)
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                # Double check: sometimes content takes a bit longer to pop in
                self.random_wait(1, 2)
                if page.evaluate("document.body.scrollHeight") == last_height:
                    print(f" [SmartScroll] Reached bottom after {attempt+1} scrolls.")
                    break
            last_height = new_height
            if attempt % 3 == 0: print(f"  ... scrolling deeper (Attempt {attempt+1})")
        return last_height

    def verify_post_on_page(self, page, current_username, ai_reply):
        """
        Verifies if the bot's post is actually visible on the page.
        Returns True if found, False otherwise.
        """
        print(" [Verify] Searching for Proof of Work on page...")
        
        # FIRST: Check for pending/approval messages (common on moderated forums)
        pending_messages = [
            'awaiting approval', 'pending approval', 'awaiting moderation',
            'will appear after approval', 'held for moderation', 'submitted for review',
            'pending review', 'under review', 'waiting for approval'
        ]
        page_text_lower = page.content().lower()
        for msg in pending_messages:
            if msg in page_text_lower:
                print(f" [Verify] PENDING POST DETECTED: '{msg}' - treating as successful.")
                return True
        
        # 1. Ensure we are at the bottom
        self.smart_scroll(page, max_attempts=3, wait_time=1)
        
        # 2. Collect all potential aliases for self-check
        check_names = set([n.lower() for n in self.bot_aliases])
        if current_username and current_username != "unknown":
            check_names.add(current_username.lower())
            
        # 3. Check specific post blocks
        latest_posts = page.query_selector_all('.topic-post, .ipsComment, .ipsType_richText, .cooked')
        reply_chunk = ai_reply[:40].lower().strip()
        
        for p_block in latest_posts:
            try:
                # FIRST: Check for "Edit" button ownership - most reliable
                edit_btn = p_block.query_selector('.edit-post, .fa-pencil-alt, button:has-text("Edit"), .ipsComment_controls li a[href*="do=edit"]')
                p_text = p_block.inner_text().lower()
                
                if reply_chunk in p_text:
                    if edit_btn:
                        print(f" [Verify] POSITIVE MATCH: Post contains reply chunk and Edit button ownership.")
                        return True
                    
                    # If no edit button, check for alias matches
                    if any(name in p_text for name in check_names):
                        print(f" [Verify] POSITIVE MATCH: Found alias and reply chunk in a post block.")
                        return True
            except: continue

        # 4. Global content search (Fallback)
        page_html = page.content().lower()
        if reply_chunk in page_html:
            # Check if at least one of our aliases is present on the page near the reply
            if any(name in page_html for name in check_names):
                print(" [Verify] Post found via global content search.")
                return True

        return False

    def random_wait(self, min_sec=3, max_sec=7):
        time.sleep(random.uniform(min_sec, max_sec))

    def get_current_ip(self):
        """Fetches and displays the public IP address."""
        print("\n [Network] Checking connection status...")
        try:
            # Using ifconfig.me which is simple and reliable for plain text IP
            with urllib.request.urlopen("https://api.ipify.org", timeout=10) as response:
                ip = response.read().decode('utf-8').strip()
                print(f" [Network] YOUR CURRENT IP: {ip}")
                return ip
        except Exception as e:
            print(f" [Network] Warning: Could not detect public IP: {e}")
            return "unknown"

    def extract_post_id(self, url):
        if not url: return None
        url_lower = url.lower()
        
        # CATEGORY SAFETY: If it looks like a forum/category index, it's NOT a post
        category_markers = ['/forum/', '/forums/', '/c/', 'viewforum.php', 'forumdisplay.php', 'category']
        if any(marker in url_lower for marker in category_markers):
            # Exception: WordPress sometimes has /forum/ in topic URLs? No, usually it's /topic/
            # But let's be safe and only skip if it's strictly a category structure
            if not any(x in url_lower for x in ['/topic/', '/t/', 'viewtopic.php', 'showthread.php']):
                return None

        # 0. Query Parameter ID (common in vBulletin/phpBB: ?t=123 or ?p=123)
        parsed = urlparse(url)
        from urllib.parse import parse_qs
        qs = parse_qs(parsed.query)
        if 't' in qs: return qs['t'][0]
        if 'p' in qs: return qs['p'][0]
        if 'postid' in qs: return qs['postid'][0]
        if 'threadid' in qs: return qs['threadid'][0]

        # 1. Standard Discourse / Numeric IDs (e.g., /t/topic-name/1234)
        match = re.search(r'/t/[^/]+/(\d+)', url)
        if match: return match.group(1)
        
        # 2. Numeric Slash ID (e.g., /1234)
        match = re.search(r'/(\d+)(?:\?|$)', url)
        if match: return match.group(1)
        
        # 3. WordPress/bbPress Slug IDs (e.g., /topic/slug-name/)
        match = re.search(r'/topic/([^/]+)/?', url)
        if match: return match.group(1).rstrip('/')
        
        # 4. Fallback: Slug-based ID from last path component
        path = parsed.path.strip('/')
        if path:
            parts = path.split('/')
            last_part = parts[-1]
            if last_part and last_part not in ['support', 'forum', 'forums', 'topic', 'topics', 'viewforum', 'forumdisplay']:
                # Ensure it doesn't look like a direct category
                if len(parts) > 1 and parts[-2] in ['forum', 'forums', 'c']:
                    # If the parent is 'forum', it's likely a category unless we KNOW better
                    # For IPS, /forum/XYZ is a category, /topic/XYZ is a post.
                    return None 
                return last_part
        return None

    def is_post_solved(self, page):
        solved_indicators = [
            '.topic-status-info[title*="Solved" i]',
            '.topic-status-info[title*="solved" i]',
            '[data-topic-status="solved"]',
            '.solved-badge',
            '.solved-indicator',
            'i.fa-check-square',
            '.accepted-answer', # Re-enabling with check on actual visibility
            '.has-accepted-answer',
            'span.solved',
            '.d-icon-check-square', # Discourse specific
            '.solution-mark',
        ]
        
        for sel in solved_indicators:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    print(f" Post is Solved (detected by selector: {sel})")
                    return True
            except: continue

        try:
            content = page.inner_text('body').lower()
            if 'solved by' in content or 'solution accepted' in content:
                # Extra check to avoid false positives in regular text
                if page.query_selector('.topic-body:has-text("Solved by")') or \
                   page.query_selector('.cooked:has-text("Solved by")') or \
                   page.query_selector('.accepted-solution'):
                    print(" Post is Solved (detected by 'Solved by' text/badge)")
                    return True
        except: pass
        
        return False

    # ===========================
    # Cloudflare / Captcha Handling
    # ===========================
    def handle_cloudflare(self, page):
        """
        Attempts to bypass Cloudflare 'Verify you are human' challenge
        """
        try:
            print(f" checking for Cloudflare/Security challenge... (Title: '{page.title()}')")
            # Check for Cloudflare title, text, OR iframe directly
            is_challenge = False
            
            try:
                # Expanded matching for Cloudflare / Turnstile / Generic Captcha
                if "verify you are human" in page.title().lower(): is_challenge = True
                elif "just a moment" in page.title().lower(): is_challenge = True
                elif page.query_selector('text="Verify you are human"'): is_challenge = True
                elif page.query_selector('text="needs to review the security of your connection"'): is_challenge = True
                elif page.query_selector('iframe[src*="cloudflare"]'): is_challenge = True
                elif page.query_selector('iframe[src*="turnstile"]'): is_challenge = True
                elif page.query_selector('.cf-turnstile'): is_challenge = True
                elif page.query_selector('#challenge-stage'): is_challenge = True
                elif page.query_selector('#cf-wrapper'): is_challenge = True
            except Exception as e:
                # If checking title/selectors fails (e.g. target closed), just return
                print(f" Could not check for Cloudflare (page might be closed/loading): {e}")
                return False
            
            if is_challenge:
                print("[!] Cloudflare/Security challenge detected! Attempting to handle...")
                self.random_wait(3, 6)
                
                # Strategy: Iterate through ALL frames to find the checkbox
                # This is more robust than looking for specific iframe src attributes
                checkbox_found = False
                for frame in page.frames:
                    try:
                        # Check for the checkbox or the Turnstile success state
                        checkbox = frame.query_selector('input[type="checkbox"], .mark, .ctp-checkbox-label, label.ctp-checkbox-label, .big-button')
                        if checkbox and checkbox.is_visible():
                            print(f"[i] Found verification checkbox in frame, clicking with jitter...")
                            self.random_wait(1, 2)
                            
                            # Jittery Click: Click with a slight random offset
                            box = checkbox.bounding_box()
                            if box:
                                x = box['x'] + box['width'] * (0.3 + random.random() * 0.4)
                                y = box['y'] + box['height'] * (0.3 + random.random() * 0.4)
                                page.mouse.move(x + random.randint(-5, 5), y + random.randint(-5, 5))
                                self.random_wait(0.2, 0.5)
                                page.mouse.click(x, y)
                            else:
                                checkbox.click()
                                
                            print("[v] Clicked verification checkbox")
                            checkbox_found = True
                            
                            # Wait to see if it clears
                            self.random_wait(3, 5)
                            break
                    except: 
                        continue
                
                if not checkbox_found:
                    print("[!] Could not find specific checkbox in any frame. Checking for suspect frames...")
                    # Fallback: Click center of any frame that looks like Cloudflare/Turnstile
                    for frame in page.frames:
                        try:
                            if "cloudflare" in frame.url or "turnstile" in frame.url:
                                print(f"[i] Found suspect frame ({frame.url}), clicking center...")
                                # Attempt a jittery click in the center of the frame
                                # Note: frames in Playwright aren't always directly clickable via page.mouse
                                # without coordinate transformation, but frame.click('body') works.
                                frame.click('body', timeout=2000)
                                checkbox_found = True
                                break
                        except: continue

                # Wait loop to see if we get through
                print("[...] Waiting for challenge to clear...")
                for i in range(25): # Increased wait
                    self.random_wait(2, 3)
                    
                    # Check if ANY challenge indicators are still present
                    title = page.title().lower()
                    if "verify you are human" not in title and \
                       "just a moment" not in title and \
                       not page.query_selector('iframe[src*="cloudflare"]') and \
                       not page.query_selector('iframe[src*="turnstile"]') and \
                       not page.query_selector('#challenge-stage'):
                        print("[v] Challenge page seems to have cleared!")
                        return True
                    
                    # If we are stuck, try verifying again periodically
                    if i % 5 == 0:
                         print("   ...still stuck, looking for clickables again...")
                         # Re-scan for checkbox in case it loaded late
                         for frame in page.frames:
                            try:
                                if "cloudflare" in frame.url or "turnstile" in frame.url:
                                    # Try clicking body of suspect frame
                                    frame.click('body', timeout=1000)
                                    # Or checkbox if resolved
                                    cb = frame.query_selector('input[type="checkbox"]')
                                    if cb: cb.click()
                            except: pass
                         
                         
                    print(f"   ...still waiting ({i+1}/20) - Title: '{page.title()}'")
                
                print(" Auto-solve didn't clear the challenge.")
                print(" MANUAL INTERVENTION REQUIRED: Please solve the Captcha in the browser window!")
                
                # Infinite (or long) wait for user to solve it
                for i in range(120): # Wait up to 240 seconds (4 minutes)
                    self.random_wait(2, 3)
                    title = page.title().lower()
                    
                    if "verify you are human" not in title and \
                       "just a moment" not in title and \
                       not page.query_selector('iframe[src*="cloudflare"]') and \
                       not page.query_selector('iframe[src*="turnstile"]') and \
                       not page.query_selector('#challenge-stage'):
                        print("[v] Challenge cleared manually! Resuming...")
                        return True
                        
                        print(f"   ...waiting for you to solve it ({i*2}s elapsed)...")
                        
                print("[!] Manual wait timed out. Proceeding anyway (might fail)...")

        except Exception as e:
            print(f"[!] Error in handle_cloudflare: {e}")
            import traceback
            traceback.print_exc()

    def find_categories(self, page):
        """
        Detects category/sub-forum links on an index page
        """
        category_selectors = [
            'a.forumtitle',     # phpBB
            'a[href*="viewforum.php"]', # phpBB
            'a[href*="forumdisplay.php"]', # vBulletin
            'a[href*="/f/"]', # XenForo / Generic
            'a.category-title', # Discourse
            'h3 a[href*="/c/"]', # Discourse
            'a.bbp-forum-link', # bbPress/WordPress
            '.forum-link a',
            '.category-list a',
            'a[href*="/forum/"]',
            'a[href*="/forums/"]'
        ]
        
        categories = []
        for sel in category_selectors:
            try:
                elements = page.query_selector_all(sel)
                for el in elements:
                    href = el.get_attribute('href')
                    text = el.inner_text().strip()
                    if href and text and len(text) > 2:
                        # Filter out common non-category links and sorting/junk parameters
                        junk_params = ['login', 'register', 'search', 'faq', 'sortby', 'sortdirection', 'do=', 'action=', 'report', 'st=', 'sd=']
                        if any(x in href.lower() for x in junk_params):
                            continue
                        
                        # Avoid links with too many query params (usually sorting/filtering)
                        if href.count('?') > 0 and 'forum' in href.lower():
                             # If it has a query but isn't a direct forum link, skip
                             if not any(x in href.lower() for x in ['f=', 'forumid=']):
                                 continue

                        categories.append((text, href))
            except: continue
        
        # Remove duplicates
        seen = set()
        unique_categories = []
        for text, href in categories:
            if href not in seen:
                unique_categories.append((text, href))
                seen.add(href)
        
        return unique_categories

    def handle_overlays(self, page):
        """
        Removes common cookie banners, modals, and overlays that might block clicking
        """
        try:
            # Common selectors for cookie banners and distracting overlays
            overlay_selectors = [
                '#iubenda-cs-banner', 
                '.iubenda-cs-banner',
                '.cookielawinfo-cookie-combined-mask',
                '.cookie-banner-root',
                '#truste-consent-track',
                '.modal-backdrop',
                '.d-modal__backdrop',
                '.modal-container',
                'div[class*="modal-backdrop"]',
                '.fc-consent-root',
                'div[role="alertdialog"]',
                '.consent-banner',
                '#onetrust-banner-sdk',
                '[data-tid="modal-overlay"]',
                '.modal-type-cookie-consent',
                '[data-tid="modal-background"]',
                '.modal-overlay',
                '.modal-backdrop'
            ]
            
            for selector in overlay_selectors:
                try:
                    # Remove it entirely from the DOM to be safe
                    page.evaluate(f"() => {{ const el = document.querySelector('{selector}'); if (el) el.remove(); }}")
                except: pass
            
            # PROACTIVE: Click "Accept all" if still visible (Opera style)
            try:
                # Use OneTrust and common patterns
                accept_btns = [
                    '#onetrust-accept-btn-handler',
                    '#accept-all',
                    'button:has-text("Accept all")',
                    'button:has-text("Accept Selection")',
                    'button:has-text("Agree")',
                    '#consent-accept'
                ]
                for btn_sel in accept_btns:
                    btn = page.query_selector(btn_sel)
                    if btn and btn.is_visible():
                        print(f" Found cookie consent button ({btn_sel}), clicking...")
                        btn.click(timeout=3000)
                        self.random_wait(1, 2)
            except: pass

            # Additional JS to fix scroll locking often caused by modals
            page.evaluate("() => { if (document.body) { document.body.style.overflow = 'auto'; document.body.style.pointerEvents = 'auto'; } }")
        except: pass

    # ===========================
    # Robust login with retry
    # ===========================
    def login_huggingface(self, page, platform_url):
        """
        Adaptive Login Strategy
        """
        if getattr(config, 'SKIP_LOGIN', False):
            print(" SKIP_LOGIN is enabled. Proceeding in Guest Mode...")
            return True

        print(f" Attempting login for {platform_url}...")
        
        # Determine which email/password to use based on URL
        # Support both old string format and new dict format
        account_entry = None
        for key, val in accounts_config.URL_ACCOUNTS.items():
            if key in platform_url:
                account_entry = val
                break
        
        email_to_use = config.EA_EMAIL
        pass_to_use = config.EA_PASSWORD
        
        if account_entry:
            if isinstance(account_entry, dict):
                email_to_use = account_entry.get("email", config.EA_EMAIL)
                pass_to_use = account_entry.get("password", config.EA_PASSWORD)
            else:
                email_to_use = account_entry
        
        self.current_email = email_to_use
        print(f" [Multi-Account] Using credentials: {email_to_use} (Custom Password: {'Yes' if account_entry and isinstance(account_entry, dict) and 'password' in account_entry else 'No'})")
        
        # High-level retry loop for the entire login process
        for main_attempt in range(3):
            try:
                if main_attempt > 0:
                    print(f" [Retry] Login failed previously, reloading page (Attempt {main_attempt+1}/3)...")
                    page.goto(platform_url, wait_until="domcontentloaded", timeout=60000)
                    self.random_wait(3, 6)
                    self.handle_cloudflare(page)
                # High-confidence indicators that we ARE definitely logged in
                high_confidence_indicators = [
                    '.qa-user-button', '.qa-header-user-menu', '.qa-profile-picture', # Figma/Insided
                    'a.logout-link', 'a:has-text("Log Out")', 'a:has-text("Logout")',
                    '#wp-admin-bar-my-account', '.current-user', '#current-user'
                ]
                
                # General indicators that might need a double-check
                general_indicators = [
                    '.user-menu-toggle.logged-in', '#wpadminbar', 
                    '[component="user/menu"]', 'a#elUserLink', '#elUserNav', '.ipsUserPhoto',
                    '[data-role="userBar"]', '.ipsType_break[href*="/profile/"]',
                    'button:has-text("Create new project")', 'a[href*="/home/projects"]'
                ]
                
                # FIX: Define Success Indicators for verification usage later
                success_indicators = high_confidence_indicators + general_indicators

                # Pre-login Check: Already logged in?
                is_logged_in = False
                is_high_confidence = False
                
                for sel in high_confidence_indicators:
                    if page.query_selector(sel):
                        is_logged_in = True
                        is_high_confidence = True
                        break
                
                if not is_logged_in:
                    for sel in general_indicators:
                        if page.query_selector(sel):
                            is_logged_in = True
                            break
                
                # Secondary Check: If we see a "Log in" button, we are NOT logged in
                # BUT: skip this check if we already have HIGH confidence that we are logged in (e.g. saw a profile pic)
                if is_logged_in and not is_high_confidence:
                    login_btn_selectors = [
                        '.qa-header-login-button', # Figma Specific (Correct one)
                        '#elUserSignin' # IPS
                        # Note: we removed generic 'Log in' from here to avoid false negatives from footer links
                    ]
                    for btn_sel in login_btn_selectors:
                        btn = page.query_selector(btn_sel)
                        if btn and btn.is_visible():
                            print(f" Detected '{btn_sel}', so we are NOT actually logged in.")
                            is_logged_in = False
                            break
                
                if is_logged_in:
                    print(f" Correct: Already logged in detected.")
                    return True

                # Step 1: Click 'Log in' or 'Sign in'
                print(" Looking for Login/Sign in button...")
                
                # Selectors prioritized: Log in -> Sign in -> Existing user
                login_selectors = [
                    '.qa-header-login-button', # Figma Specific
                    'button:has-text("Log in"), a:has-text("Log in"), .login-button, button:has-text("Login"), a:has-text("Login"), .operaLoginButton',
                    'button:has-text("Sign in"), a:has-text("Sign in"), button:has-text("Sign In"), a:has-text("Sign In")',
                    '[aria-label="Sign in"], [aria-label="Log in"], [aria-label="Login"]',
                    '.sign-in-button, .btn-login, .login-btn',
                    'a.operaLoginButton',
                    # "Existing user? Sign In" type links
                    'a:has-text("Existing user"), button:has-text("Existing user")',
                    'a:has-text("Already have an account")'
                ]

                login_btn = None
                for sel in login_selectors:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        # Sanity check: ensure it's not a pure Sign Up button
                        # specific exclusion for buttons that might strictly be "Sign Up" but matched loosely
                        text = btn.inner_text().strip().lower()
                        # CRITICAL: Sanity check for text length - login buttons are usually short
                        # This prevents clicking on long post titles that happen to contain the word "Login"
                        if len(text) > 30 and sel != '.qa-header-login-button':
                            continue
                            
                        if ("sign up" in text or "create account" in text) and "sign in" not in text and "log in" not in text and "login" not in text:
                            continue
                            
                        login_btn = btn
                        print(f" Found login button with selector: {sel}")
                        break

                # --- ANTIGRAVITY COMPONENT 1: Checkbox Fix (from Remote Repo) ---
                print(" [Antigravity] Checking for 'I agree' or 'Terms' checkboxes...")
                checkbox_selectors = [
                    'input[type="checkbox"]', 
                    'input#tos', 
                    'input#agree', 
                    '.d-checkbox',
                    'label:has-text("agree")', 
                    'label:has-text("terms")'
                ]
                for cb_sel in checkbox_selectors:
                    try:
                        cb = page.query_selector(cb_sel)
                        if cb and cb.is_visible() and not cb.is_checked():
                            print(f" [Antigravity] Clicking required checkbox: {cb_sel}")
                            cb.click()
                            self.random_wait(1, 2)
                    except: pass
                # ----------------------------------------------

                if login_btn:
                    text = login_btn.inner_text().strip().replace('\n', ' ')
                    print(f" Clicking Login/Sign in button: '{text}'")
                    
                    # Robust click for buttons that might be hidden or outside viewport
                    try:
                        login_btn.scroll_into_view_if_needed()
                        login_btn.click(timeout=5000)
                    except Exception as e:
                        print(f" Click failed ({e}), trying force click...")
                        try:
                            login_btn.click(force=True, timeout=5000)
                        except:
                            print(" Force click failed, trying JS click...")
                            login_btn.evaluate("el => el.click()")

                # Longer wait for bubble.io and similar forums
                self.random_wait(4, 6)
                
                # Check for Cloudflare/Captcha immediately after clicking login
                # The interaction might trigger a security check
                self.handle_cloudflare(page)
                if page.is_closed(): return False

                # Step 2: Adaptive Check - Look for "Login with email" OR direct fields
                print(" Checking for login options (Email button or Direct fields)...")
                
                # Clear overlays again on the new page/modal
                self.handle_overlays(page)
                
                # Wait a moment for modal to animate in
                self.random_wait(2, 4)

                # Try to find "Login with email" button
                # Discourse often uses specific classes or text "with Email"
                login_email_btn_selectors = [
                    'button.login-with-email', 
                    'button:has-text("Login with email")', 
                    'button:has-text("with Email")',
                    '.btn-social.email', 
                    'button[title*="email"]',
                    'button:has-text("Confirm")', # Opera specific
                    'button:has-text("Continue")',  # Generic fallback for multi-step
                    # Cursor / Discourse specific
                    'button.btn-social.email',
                    'button.btn-login-with-email',
                    'button:has-text("Log in with email")',
                    '#login-buttons .email'
                ]
                
                login_email_btn = None
                for sel in login_email_btn_selectors:
                    login_email_btn = page.query_selector(sel)
                    if login_email_btn and login_email_btn.is_visible():
                        print(f" Found 'Login with email' button ({sel}), clicking...")
                        
                        # One last check before clicking
                        self.handle_overlays(page)
                        
                        try:
                            login_email_btn.click(timeout=3000)
                        except:
                            login_email_btn.evaluate("el => el.click()")
                        self.random_wait(2, 4)
                        break
                
                # Step 3: Find fields (retry loop)
                print(" Looking for input fields...")
                self.handle_overlays(page)
                email_field = None
                pass_field = None
                for attempt in range(5):
                    # Expanded selectors to include placeholder-based matching (Flarum style)
                    email_selectors = [
                        'input[type="email"]:not(#emailsignup)', # Bubble.io trap exclusion
                        'input#login-account-name',
                        '#user_login',
                        'input[name="username"]',
                        'input[name="user"]',
                        'input[type="text"][name="login"]',
                        'input[type="text"][name="log"]',
                        'input[name="email"]', 
                        'input[type="email"]',
                        'input[type="text"][name*="user"]',
                        'input[placeholder*="Username"]',
                        'input[placeholder*="Email"]',
                    ]
                    
                    pass_selectors = [
                        'input#login-password', # Bubble.io specific
                        '#user_pass',
                        'input[name="pwd"]',
                        'input[name="password"]',
                        'input#login-account-password',
                        'input[type="password"]',
                        'input[placeholder*="Password"]',
                    ]
                    
                    # Try each email selector
                    for sel in email_selectors:
                        field = page.query_selector(sel)
                        if field and field.is_visible() and field.is_editable():
                            email_field = field
                            print(f" Found email field with selector: {sel}")
                            break
                    
                    # Try each password selector
                    for sel in pass_selectors:
                        field = page.query_selector(sel)
                        if field and field.is_visible() and field.is_editable():
                            pass_field = field
                            print(f" Found password field with selector: {sel}")
                            break
                    
                    if email_field and pass_field:
                        break
                    self.random_wait(1, 2)
                
                # Step 4: Layered Field Filling (Handles standard, multi-step, and complex forms)
                fields_already_filled = False
                if email_field:
                    print(f" Filling email/username...")
                    # Use robust JS fill for email
                    email_field.evaluate("""(el, val) => {
                        el.focus();
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        nativeInputValueSetter.call(el, val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        // Don't blur immediately for multi-step forms
                    }""", email_to_use)
                    self.random_wait(1, 2)
                    
                    # Check if password field is missing/hidden (Multi-step login)
                    if not pass_field or not pass_field.is_visible():
                        print(" Password field hidden/missing. Checking for 'Continue' / 'Next' button...")
                        continue_selectors = [
                            'button:has-text("Continue")',
                            'button:has-text("Next")',
                            'button:has-text("Proceed")',
                            'div:has-text("Continue")',   # Asana
                            '[role="button"]:has-text("Continue")',
                            '.LoginEmailForm-continueButton', # Asana specific
                            'button[type="submit"]',
                            'input[type="submit"]',
                            '.btn-primary:has-text("Continue")',
                            '[id*="continue"]',
                            '[class*="continue"]'
                        ]
                        
                        found_continue = False
                        for sel in continue_selectors:
                            btn = page.query_selector(sel)
                            if btn and btn.is_visible():
                                print(f" Found navigation button ({sel}), attempting robust click...")
                                try:
                                    # Standard click
                                    btn.click(timeout=3000)
                                    found_continue = True
                                except:
                                    try:
                                        # JS fallback click
                                        print(f"   Standard click failed, trying JS click for {sel}...")
                                        btn.evaluate("el => el.click()")
                                        found_continue = True
                                    except: pass
                                
                                if found_continue:
                                    self.random_wait(2, 4)
                                    # Double check: Did password field appear? If not, try Enter key.
                                    page.wait_for_timeout(1000)
                                    p_field = None
                                    for ps in pass_selectors:
                                        if page.query_selector(ps):
                                            p_field = page.query_selector(ps)
                                            if p_field and p_field.is_visible(): break
                                    
                                    if not p_field:
                                        print("   Password field still not visible after click, ensuring focus and trying 'Enter' key fallback...")
                                        try:
                                            email_field.focus()
                                            self.random_wait(0.5, 1)
                                        except: pass
                                        page.keyboard.press("Enter")
                                        self.random_wait(3, 5)
                                    break
                        
                        if found_continue:
                            print(" Waiting for password field to appear...")
                        else:
                            print(" 'Continue' button not found via selectors, ensuring focus and trying 'Enter' key fallback...")
                            try:
                                email_field.focus()
                                self.random_wait(0.5, 1)
                            except: pass
                            page.keyboard.press("Enter")
                            found_continue = True # Assume it worked and wait
                            self.random_wait(3, 5)

                        if found_continue:
                            print(" Waiting for password field to appear...")
                            for _ in range(5):
                                for sel in pass_selectors:
                                    field = page.query_selector(sel)
                                    if field and field.is_visible():
                                        pass_field = field
                                        print(f" Found password field after 'Continue' click!")
                                        break
                                if pass_field: break
                                self.random_wait(1, 2)
                
                if pass_field:
                    print(f" Filling password...")
                    # Use robust JS fill for password
                    pass_field.evaluate("""(el, val) => {
                        el.focus();
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                        nativeInputValueSetter.call(el, val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.blur();
                    }""", config.EA_PASSWORD)
                    self.random_wait(1, 2)
                    fields_already_filled = True
                else:
                    # Step 4.5: If password field is STILL not found, try common fallbacks
                    # Strategy: Some sites (like bubble.io) require clicking "Log in" a second time inside a modal/redirect.
                    print(" Password field not found, trying common platform fallbacks...")
                    second_login_selectors = [
                        'button:has-text("Log in")',
                        'a:has-text("Log in")',
                        '.login-button',
                        'button:has-text("log in")',
                        'button:has-text("LOGIN")',
                        'button:has-text("Sign In")', # Vintagestory
                        'button.ipsButton_primary',   # IPS/Invision
                        'button[type="submit"]',
                        'input[type="submit"]',
                        '.btn:has-text("Log")',
                        'button.btn-primary'
                    ]
                    
                    second_login_btn = None
                    for sel in second_login_selectors:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            print(f"   Found button with selector: {sel}")
                            second_login_btn = btn
                            break
                    
                    if second_login_btn:
                        print(" Clicking 'Log in' button again...")
                        second_login_btn.click()
                        
                        # Wait for page reload to complete (fixes bubble.io reload issue)
                        print(" Waiting for page reload to complete...")
                        try:
                            # Wait for DOM to be ready
                            page.wait_for_load_state("domcontentloaded", timeout=15000)
                            # Wait for network activity to settle (useful if page reloads)
                            page.wait_for_load_state("networkidle", timeout=15000)
                        except Exception as e:
                            print(f" Wait for load state timed out ({str(e)[:50]}), proceeding with manual wait...")

                    # Extra safety wait
                    self.random_wait(4, 6)
                    
                    # Retry finding fields after second click with expanded selectors
                    # Fill immediately when found to prevent page reload
                    for attempt in range(10):  # Increased attempts
                        print(f" Attempt {attempt + 1}/10 to find fields...")
                        
                        # Try each email selector
                        for sel in email_selectors:
                            field = page.query_selector(sel)
                            if field:
                                print(f"   Found element with {sel}")
                                try:
                                    # React/Framework robust fill using native property setter
                                    # This bypasses React's value-setter wrapper to ensure state updates
                                    field.evaluate("""(el, val) => {
                                        el.focus();
                                        
                                        // Get native setter (bypass framework overrides)
                                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                        nativeInputValueSetter.call(el, val);
                                        
                                        el.dispatchEvent(new Event('input', { bubbles: true }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                        el.blur();
                                    }""", email_to_use)
                                    
                                    # Verify if value stuck
                                    current_val = field.evaluate("el => el.value")
                                    if current_val == email_to_use:
                                        email_field = field
                                        print(f" Filled & Verified email field using JS: {sel}")
                                        break
                                    else:
                                        print(f" JS Fill appeared to fail, value is: '{current_val}'")
                                        
                                except Exception as e:
                                    print(f"   Failed to fill: {str(e)[:100]}")
                        
                        # Try each password selector
                        for sel in pass_selectors:
                            field = page.query_selector(sel)
                            if field:
                                print(f"   Found element with {sel}")
                                try:
                                    # React/Framework robust fill using native property setter
                                    field.evaluate("""(el, val) => {
                                        el.focus();
                                        
                                        // Get native setter (bypass framework overrides)
                                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                                        nativeInputValueSetter.call(el, val);
                                        
                                        el.dispatchEvent(new Event('input', { bubbles: true }));
                                        el.dispatchEvent(new Event('change', { bubbles: true }));
                                        el.blur();
                                    }""", config.EA_PASSWORD)
                                    
                                    # Verify if value stuck
                                    current_val = field.evaluate("el => el.value")
                                    if current_val == config.EA_PASSWORD:
                                        pass_field = field
                                        print(f" Filled & Verified password field using JS: {sel}")
                                        break
                                    else:
                                        print(f" JS Fill appeared to fail, value is: '{current_val}'")

                                except Exception as e:
                                    print(f"   Failed to fill: {str(e)[:100]}")
                        
                        if email_field and pass_field:
                            print(f" Fields found and filled after second 'Log in' click")
                            fields_already_filled = True
                            break
                        self.random_wait(1, 2)

                # Step 5: Fill credentials (NOT NEEDED, ALREADY HANDLED ABOVE)
                
                # Submit login
                if email_field and pass_field:
                    print(" verifying fields are still filled before submitting...")
                    try:
                        # Check if fields are still valid (page didn't reload) and filled
                        e_val = email_field.evaluate("el => el.value")
                        p_val = pass_field.evaluate("el => el.value")
                        
                        if e_val != email_to_use or p_val != pass_to_use:
                            print(" Fields lost their values (page reload?), refilling...")
                            # Refill
                            email_field.evaluate(f"el => el.value = '{email_to_use}'")
                            email_field.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
                            pass_field.evaluate(f"el => el.value = '{pass_to_use}'")
                            pass_field.evaluate("el => el.dispatchEvent(new Event('input', { bubbles: true }))")
                    except Exception as e:
                        print(f" Error verifying fields (stale element?): {e}")
                        # If stale, we should probably return False and let the loop retry or crash? 
                        # For now, let's just try to press enter as a hail mary
                    
                    # Try to find specific submit button first (better than Enter)
                    print(" Looking for Submit/Log in button...")
                    submit_buttons = [
                        'button.login-button', 
                        'button:has-text("Log in")', 
                        'input[type="submit"]', 
                        'button.btn-primary',
                        '.modal button:has-text("Log in")',
                        'div.LoginPasswordForm-loginButton',  # Asana
                        'div:has-text("Log in")',              # Asana
                        '[role="button"]:has-text("Log in")',  # Generic
                        'button:has-text("Sign in")',
                        '.ipsButton_primary:has-text("Sign In")' # Vintagestory
                    ]
                    
                    clicked = False
                    for sel in submit_buttons:
                        btns = page.query_selector_all(sel)
                        for btn in btns:
                            if btn.is_visible():
                                # Avoid clicking the "Log in" link at the top (header)
                                # Heuristic: Submit buttons usually inside forms/modals
                                if "header" in btn.evaluate("el => el.className"): 
                                    continue
                                
                                print(f" Found likely submit button ({sel}), clicking...")
                                try:
                                    btn.click(timeout=3000)
                                    clicked = True
                                    break
                                except:
                                    try:
                                        print(f" Click failed, trying JS click for {sel}...")
                                        btn.evaluate("el => el.click()")
                                        clicked = True
                                        break
                                    except: pass
                        if clicked: break
                    
                    if not clicked:
                        # Strategy 1: Press Enter (Fallback)
                        print(" Submit button not found/clickable, ensuring focus and pressing 'Enter'...")
                        try:
                            if pass_field:
                                pass_field.focus()
                                self.random_wait(0.5, 1)
                        except: pass
                        page.keyboard.press("Enter")
                    
                    self.random_wait(4, 6)

                    submit_btn = page.query_selector(
                        'button#login-button, button:has-text("Log in"), button:has-text("Sign In"), .login-button[type="submit"], .btn-primary[type="submit"], button.ipsButton_primary'
                    )
                    if submit_btn:
                        print(" Found submit button, attempting click just in case...")
                        try:
                            # Try normal click first
                            submit_btn.click()
                        except:
                            try:
                                # Try force click
                                print(" Normal click failed, trying force click...")
                                submit_btn.click(force=True)
                            except:
                                # Fallback to JS click
                                print(" Force click failed, trying JS click...")
                                submit_btn.evaluate("element => element.click()")
                            
                    print(" Waiting for login to complete...")
                    self.random_wait(10, 15)
                    
                    # Verify login - stricter checks
                    is_logged_in = False
                    for sel in success_indicators:
                        if page.query_selector(sel):
                            is_logged_in = True
                            print(f" Login successful (verified by: {sel})")
                            break
                    
                    # Proactive Verification: If not verified yet, try to click profile icons to see if menu contains "Log out"
                    if not is_logged_in:
                        print(" Initial verification failed, trying proactive profile-menu check...")
                        profile_icon_selectors = [
                            '.header-dropdown-toggle.current-user', 
                            '#current-user',
                            '.user-menu-toggle',
                            '.ipsUserPhoto',
                            '#elUserLink',
                            '.header-user-avatar',
                            'button:has-text("Account")',
                            '.header .user-icon', 
                            'img[alt*="avatar"]'
                        ]
                        for p_sel in profile_icon_selectors:
                            p_icon = page.query_selector(p_sel)
                            if p_icon and p_icon.is_visible():
                                print(f"   Clicking suspected profile icon ({p_sel}) to verify login...")
                                try:
                                    p_icon.click(timeout=3000)
                                    self.random_wait(1, 2)
                                    # Check for logout/account text in the now-open menu
                                    menu_indicators = ['Log out', 'Account', 'Home', 'Billing', 'Log Out']
                                    for m_ind in menu_indicators:
                                        if page.query_selector(f'*:has-text("{m_ind}")'):
                                            print(f"   Verified login via profile menu item: {m_ind}")
                                            is_logged_in = True
                                            break
                                    if is_logged_in: break
                                except: pass

                    if is_logged_in:
                        # --- POST-LOGIN SESSION SYNC (SSO) ---
                        # If we logged in on a different page (e.g. bubble.io), we need to ensure the forum is synced.
                        if platform_url not in page.url:
                            print(f" [Sync] Navigating back to forum to activate session: {platform_url}")
                            page.goto(platform_url, wait_until="domcontentloaded", timeout=60000)
                            self.random_wait(5, 8)
                            
                            # First: Check if we are ALREADY logged in (No sync needed)
                            is_now_logged_in = False
                            for s_ind in success_indicators:
                                if page.query_selector(s_ind):
                                    print(f" [Sync] Success! Already logged in on forum after redirection.")
                                    is_now_logged_in = True
                                    break
                            
                            if is_now_logged_in:
                                return True

                            # Second: If still logged out, click "Log in" once to trigger SSO sync
                            print(" [Sync] Still not logged in on forum, checking for sync button...")
                            sync_selectors = ['button:has-text("Log in")', 'a:has-text("Log in")', '.login-button']
                            for sync_sel in sync_selectors:
                                sync_btn = page.query_selector(sync_sel)
                                if sync_btn and sync_btn.is_visible():
                                    print(f" [Sync] Found '{sync_sel}', clicking once more to activate local session...")
                                    try:
                                        sync_btn.click(timeout=5000)
                                        self.random_wait(5, 8)
                                        # Verify one last time
                                        for s_indicator in success_indicators:
                                            if page.query_selector(s_indicator):
                                                print(f" [Sync] Session activated successfully!")
                                                return True
                                    except: pass
                        # ------------------------------------
                        
                        return True
                    else:
                        print(" Login verification failed (success indicators not found)")
                        return False

                print(" Could not find email/password fields")
                # Fallback: Check for Cloudflare one more time, maybe it appeared after clicking login
                self.handle_cloudflare(page)
                
                print(" Login failed - Input fields not found")
                return False

            except Exception as e:
                print(f" [Error] Login attempt {main_attempt+1} failed: {e}")
                if main_attempt == 2: # Last attempt
                    print(" [X] All login attempts failed. Skipping forum.")
                    return False
                self.random_wait(5, 10) # Wait before retry

        return False

    # ===========================
    # Main task runner
    def check_notifications(self, page):
        """
        Ultra-robust notification scraper for Cursor/Discourse.
        Scans all visible menu items and filters by icons/classes.
        """
        priority_urls = []
        print(" [Notifications] Checking for direct interactions...")
        
        try:
            # 1. Detect if menu is already open (prevents double-clicking and closing it)
            is_open = page.query_selector('.menu-panel, .user-menu, .ipsMenu')
            
            if not is_open:
                # Look for the Notification Bell or User Menu
                bell_selectors = [
                    '#current-user.header-dropdown-toggle', 
                    '.header-dropdown-toggle.current-user',
                    '.notifications-dropdown', 
                    'a.notifications',
                    '#elFullNotifications'
                ]
                
                bell = None
                for sel in bell_selectors:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        bell = el
                        break
                
                if bell:
                    print(" [Notifications] Opening menu...")
                    try:
                        bell.click(timeout=3000)
                    except:
                        bell.evaluate("el => el.click()")
                    self.random_wait(2, 4)
            
            # 2. Extract Links - Be very aggressive
            # Check for any list items in common container types
            print(" [Notifications] Scanning menu items...")
            
            # Extract all links inside the menu panel
            # Discourse items usually have class 'notification'
            notif_items = page.query_selector_all('.notification-list li, .menu-panel li, .user-menu li, .ipsDataItem')
            
            links_found = []
            
            for item in notif_items:
                try:
                    # Filter out "Likes" - they have Heart/Like icons
                    row_text = item.inner_text().lower()
                    row_html = item.inner_html().lower()
                    row_class = item.get_attribute('class') or ""
                    
                    if 'liked' in row_text or 'hearted' in row_text or 'reaction' in row_text:
                        continue
                    if 'notification liked' in row_class:
                        continue
                        
                    # Filter out system/automated messages
                    if 'system' in row_text or 'staff' in row_text or 'earned' in row_text or 'badge' in row_text:
                        # Double check it's an automated message, not just a mention of "system"
                        # Usually trust levels or automated greetings
                        if any(x in row_text for x in ['trust level', 'promoted', 'welcome', 'spending time', 'earned', 'badge', 'rewind', 'basic', 'editor']):
                            print(f" [Notifications] Skipping automated/system/badge row: {row_text[:50]}...")
                            continue

                    # Look for icons or classes that mean "Reply" or "Mention"
                    is_valid = False
                    
                    # Discourse Classes
                    if any(x in row_class for x in ['reply', 'mention', 'quote', 'unread']):
                        is_valid = True
                    
                    # Icon Checks (using icons from screenshot: reply/at)
                    if '.d-icon-reply' in row_html or '.d-icon-at' in row_html or '.fa-reply' in row_html or '.fa-at' in row_html:
                        is_valid = True
                        
                    # Broad text check as fallback
                    if any(x in row_text for x in ['replied', 'mentioned', 'quoted']):
                        is_valid = True

                    if is_valid:
                        a = item.query_selector('a')
                        if a:
                            href = a.get_attribute('href')
                            if href:
                                # Clean the URL
                                clean_href = href.split('#')[0].split('?')[0]
                                
                                # Remove trailing post number (Discourse logic)
                                parts = clean_href.rstrip('/').split('/')
                                if parts[-1].isdigit() and len(parts) > 5:
                                    clean_href = "/".join(parts[:-1])

                                full_url = clean_href if clean_href.startswith('http') else f"{urlparse(page.url).scheme}://{urlparse(page.url).netloc}{clean_href}"
                                
                                if full_url not in links_found:
                                    print(f" [Notifications] Found priority thread: {full_url}")
                                    links_found.append(full_url)
                except Exception as e:
                    print(f" [Notifications] Issue processing item: {str(e)[:50]}")
                    continue

            for url in links_found:
                p_id = self.extract_post_id(url)
                if p_id:
                    priority_urls.append((p_id, url))
            
            print(f" [Notifications] Done. {len(priority_urls)} priority threads extracted.")
            # Only hit escape if we actually opened something and want to clear it
            page.keyboard.press("Escape")
            
        except Exception as e:
            print(f" [Notifications] Warning: Scraper issue - {e}")
            
        return priority_urls

    # ===========================
    def run_huggingface_task(self, platform_url):
        # 1. Show current IP for VPN verification
        self.get_current_ip()
        
        parsed_url = urlparse(platform_url)
        platform_name = parsed_url.netloc
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        user_data_dir = os.path.join(os.getcwd(), "bot_browser_profile")
        
        # GHOST MODE: Clear session if enabled
        if getattr(config, 'RESET_SESSION', False):
            if os.path.exists(user_data_dir):
                print(" GHOST MODE: Clearing browser profile for a fresh start...")
                try:
                    # Retry logic for cleanup in case files are locked
                    for _ in range(3):
                        try:
                            shutil.rmtree(user_data_dir)
                            break
                        except: time.sleep(1)
                except Exception as e:
                    print(f" Could not clear profile: {e}")

        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)

        # Randomized Fingerprinting
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
        ]
        viewports = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1536, 'height': 864}
        ]
        random_ua = random.choice(user_agents)
        random_vp = random.choice(viewports)

        # Proxy Logic
        proxy_server = None
        if getattr(config, 'USE_PROXY', False):
            pm = ProxyManager()
            proxy_server = pm.get_random_proxy()
            if proxy_server:
                print(f" Using Proxy: {proxy_server}")

        with sync_playwright() as p:
            # Auto-detect GitHub Actions environment
            is_github_actions = os.getenv("GITHUB_ACTIONS") == "true" or os.getenv("CI") == "true"
            print(f" [Environment] GitHub Actions: {is_github_actions}. {'Using Headless Mode.' if is_github_actions else 'Using Headed Mode (Laptop).'}")

            # Use Persistent Context to save cookies and session data (builds reputation)
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=is_github_actions, # Auto-switch: True on GitHub, False on Laptop
                proxy={"server": proxy_server} if proxy_server else None,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--start-maximized',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certifcate-errors',
                    '--no-first-run',
                    '--disable-save-password-bubble',
                    '--password-store=basic',
                ],
                ignore_default_args=['--enable-automation'], # Crucial: prevents Chrome from sending automation flags
                user_agent=random_ua,
                viewport=None # Use full window size to prevent "broken view"
            )
            
            # Advanced Anti-detection script: Mask common automation indicators
            context.add_init_script("""
                // 1. Hide webdriver
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

                // 2. Mock Hardware
                Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

                // 3. Mock Languages & Platform
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

                // 4. Fix for Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
                );
            """)
            
            # Reuse existing page if available (prevents double tabs)
            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = context.new_page()
            
            print(f"Navigating to {platform_url} (Advanced Stealth Enabled)...")
            try:
                # Increased timeout for slow forums like Webflow/Bubble
                page.goto(platform_url, wait_until="domcontentloaded", timeout=60000)
                self.random_wait(5, 8)
                
                # Check for empty/failed load
                if page.url == "about:blank" or not page.query_selector('body') or page.content().strip() == "<html><head></head><body></body></html>":
                    print("! Page appears empty/blank, attempting one reload...")
                    page.reload(wait_until="domcontentloaded", timeout=60000)
                    self.random_wait(5, 8)

                # Proactively clear overlays (Cookie banners etc)
                self.handle_overlays(page)
            except Exception as e:
                print(f"! Page load issues ({str(e)[:50]}), continuing cautiously...")

            if page.is_closed():
                print(" Page/Browser closed unexpectedly. Skipping this forum.")
                return

            # Final check before login: if still blank, skip
            if page.url == "about:blank" or page.title() == "":
                print("! Target page is still blank or titleless. Skipping this forum to avoid hangs.")
                return

            # Check for Cloudflare/Captcha immediately after load
            self.handle_cloudflare(page)
            
            if page.is_closed(): return

            if not self.login_huggingface(page, platform_url):
                print(" [CRITICAL] Login failed. Skipping all activities on this forum to protect account/reputation.")
                return
            
            print(f" Ensuring we are on: {platform_url}")
            
            # 1. PRIORITY: Check Notifications first
            priority_urls = self.check_notifications(page)
            
            # Ensure we are back on main page for discovery
            page.goto(platform_url, wait_until="domcontentloaded")
            self.random_wait(3, 5)

            # Step 6: Deep Topic Discovery (Recursive navigation)
            def get_posts_from_page(page, base_url):
                # Check for announcement/pinned markers to skip them
                post_selectors = [
                    'a.topic-title',           # Discourse
                    'a[href*="/t/"]',           # Discourse
                    'a.topictitle',            # phpBB
                    'a[href*="viewtopic.php"]', # phpBB
                    'a[href*="showthread.php"]', # vBulletin
                    'a[href*="/threads/"]',     # XenForo
                    'a.bbp-topic-permalink',   # WordPress/bbPress
                    'li.bbp-topic-title a',    # WordPress
                    '.bbp-body a[href*="/topic/"]', # WordPress
                    '.ipsDataItem_title a',    # Invision Community (IPS)
                    '[class*="title"] a[href*="/topic/"]', # IPS / Generic
                    'h3 a[href*="/topic/"]',   # Generic
                    '.topic-list-item a',
                    '.thread-title a',
                    'a[component="category/topic/title"]', # Opera / NodeBB
                    '[component="category/topic"] [component="topic/header"] a', # NodeBB / Opera
                    '[component="topic/header"] a', # NodeBB
                    'a[href^="/topic/"]' # Generic NodeBB / Opera
                ]
                posts = []
                for sel in post_selectors:
                    try:
                        elements = page.query_selector_all(sel)
                        for el in elements:
                            href = el.get_attribute('href')
                            if href:
                                full_url = href if href.startswith('http') else f"{base_url}{href}"
                                
                                # Strict Post vs Category Filter
                                if any(x in full_url.lower() for x in ['/forum/', '/c/', 'viewforum.php', 'forumdisplay.php']):
                                    # Even if matched by a selector, if it has category markers, ignore it as a post
                                    if not any(x in full_url.lower() for x in ['/topic/', '/t/', 'viewtopic.php', 'showthread.php']):
                                        continue
                                
                                # Skip pinned or announcement threads if possible
                                parent_item = el.evaluate_handle("el => el.closest('.topic-list-item')")
                                if parent_item:
                                    is_pinned = parent_item.as_element().query_selector('.pinned, .announcement, .fa-thumbtack')
                                    if is_pinned:
                                        print(f" [Skipping] Pinned/Announcement thread: {full_url}")
                                        continue

                                post_id = self.extract_post_id(full_url)
                                if post_id:
                                    if (post_id, full_url) not in posts:
                                        posts.append((post_id, full_url))
                                else:
                                    # Debug: Why was it skipped?
                                    if '/topic/' in full_url or '/t/' in full_url:
                                        print(f"    Could not extract ID from: {full_url}")
                    except: continue
                return posts

            def discover_posts_deep(page, current_url, base_url, depth=0):
                if depth > 2: # Max 3 levels deep
                    return []
                
                print(f" Searching for posts (Depth {depth})...")
                # Scroll to load
                page.evaluate("window.scrollBy(0, 1000)")
                self.random_wait(2, 4)
                
                posts = get_posts_from_page(page, base_url)
                
                # If we found posts, we are good!
                if len(posts) >= 2:
                    return posts
                
                # If few/no  posts, try navigating deeper into categories
                print(f" Few/no topics found at depth {depth}. Looking for categories...")
                category_selectors = [
                    'a.clickable-area-link', # Opera
                    'a[href^="/category/"]', # Opera / NodeBB
                    '.ipsDataItem_title a[href*="/forum/"]', # IPS
                    'a[href*="/f/"]', # Discourse
                    'h3 a' # Generic
                ]
                categories = []
                for cat_sel in category_selectors:
                    try:
                        cat_els = page.query_selector_all(cat_sel)
                        for cat_el in cat_els:
                            text = cat_el.inner_text().strip()
                            href = cat_el.get_attribute('href')
                            if text and href:
                                categories.append((text, href))
                    except: pass
                
                if categories:
                    # Pick a random category to explore, avoiding current
                    valid_categories = []
                    current_url_clean = current_url.rstrip('/')
                    for c_text, c_url in categories:
                        full_cat_url = c_url if c_url.startswith('http') else f"{base_url}{c_url}"
                        if full_cat_url.rstrip('/') != current_url_clean:
                            valid_categories.append((c_text, full_cat_url))
                    
                    if valid_categories:
                        cat_text, full_cat_url = random.choice(valid_categories)
                        print(f" [Depth {depth}] Entering: {cat_text} ({full_cat_url})")
                        try:
                            page.goto(full_cat_url, wait_until="domcontentloaded", timeout=30000)
                            self.random_wait(3, 5)
                            self.handle_overlays(page)
                            # Recursive call
                            return discover_posts_deep(page, full_cat_url, base_url, depth + 1)
                        except:
                            print(f" Failed to load category at depth {depth}")
                
                return posts # Return whatever we found if no categories or failed deeper search

            # 2. DISCOVERY: Find new posts as usual
            discovered_posts = discover_posts_deep(page, platform_url, base_url)
            
            # 3. COMBINE: Notifications first, then discovered posts
            seen_ids = set()
            post_urls = []
            
            for p_id, p_url in priority_urls:
                if p_id not in seen_ids:
                    post_urls.append((p_id, p_url))
                    seen_ids.add(p_id)
            
            for p_id, p_url in discovered_posts:
                if p_id not in seen_ids:
                    post_urls.append((p_id, p_url))
                    seen_ids.add(p_id)
            
            # --- SELF-IDENTITY DETECTION ---
            current_username = "unknown"
            
            # --- NEW: Heavy Identity Check (Meta/JS) ---
            try:
                # 1. Check discourse_username meta Tag
                meta_name = page.evaluate("() => document.querySelector('meta[name=\"discourse_username\"]')?.content")
                if meta_name:
                    current_username = meta_name
                    print(f" [Identity] Detected via Discourse Meta: {current_username}")
                
                # 2. Check JS Variables (Discourse specific)
                if current_username == "unknown":
                    js_name = page.evaluate("() => window.currentUser?.username || window.Discourse?.User?.current()?.username")
                    if js_name:
                        current_username = js_name
                        print(f" [Identity] Detected via Discourse JS: {current_username}")
            except: pass
            
            if current_username == "unknown":
                name_selectors = [
                    '#current-user .username', 
                    '#current-user a.username',
                    '.current-user b', 
                    '.user-menu-toggle .username',
                    '.header-dropdown-toggle.current-user[title]',
                    '#elUserLink', 
                    '.ipsUserPhoto', 
                    '.ipsType_break[href*="/profile/"]'
                ]
                for sel in name_selectors:
                    el = page.query_selector(sel)
                    if el:
                        # Prefer title or aria-label for Discourse
                        current_username = el.get_attribute('title') or el.get_attribute('aria-label') or el.inner_text().strip()
                        if current_username:
                            # Clean up "Rao_Athar's Account" -> "Rao_Athar"
                            current_username = current_username.split("'s")[0].replace("Account", "").strip()
                            print(f" [Identity] Detected my name via DOM: {current_username}")
                            break
            
            # Fallback for recognized aliases if detection is ambiguous or fails
            name_to_check = current_username.lower() if current_username != "unknown" else ""
            email_ref = getattr(self, 'current_email', "").lower()
            
            # If current_username is still unknown or NOT in our known aliases, cross-check
            is_recognized = any(alias.lower() in name_to_check for alias in self.bot_aliases)
            if not is_recognized:
                # Check email clues
                for alias in self.bot_aliases:
                    if alias.lower().replace("_", "") in email_ref.replace("@gmail.com", ""):
                        current_username = alias
                        print(f" [Identity] Recognized by email/alias fallback as: {current_username}")
                        break
            
            # Final Safety: If it's a known bot name but not mapped yet
            if current_username == "unknown" and "raoathar" in email_ref:
                current_username = "Rao_Athar"
                print(f" [Identity] Final Fallback: {current_username}")

            # --- NEW: Dynamic Identity Probe (Enhanced) ---
            if current_username == "unknown":
                print(" [Identity] Username still unknown. Probing via profile menu...")
                profile_selectors = [
                    '#current-user', '.user-menu-toggle', '.header-dropdown-toggle.current-user', 
                    '#elUserLink', '.ipsUserPhoto_tiny'
                ]
                for p_sel in profile_selectors:
                    p_btn = page.query_selector(p_sel)
                    if p_btn and p_btn.is_visible():
                        try:
                            # 1. Try Menu Probe
                            p_btn.click()
                            self.random_wait(2, 3)
                            expanded_selectors = ['.user-menu .username', '.dropdown-menu .username', '.ipsMenu_header .ipsType_break']
                            for ex_sel in expanded_selectors:
                                ex_el = page.query_selector(ex_sel)
                                if ex_el:
                                    current_username = ex_el.inner_text().strip()
                                    print(f" [Identity] Detected via profile menu: {current_username}")
                                    break
                            
                            # 2. Deep Identity Check: Visit Profile Page if still unknown
                            if current_username == "unknown":
                                print(" [Identity] Menu probe failed. Visiting profile page directly...")
                                profile_link_el = page.query_selector('.user-menu .username a, .dropdown-menu a[href*="/u/"], .ipsMenu_header a[href*="/profile/"]')
                                if profile_link_el:
                                    profile_url = profile_link_el.get_attribute('href')
                                    if profile_url:
                                        print(f" [Identity] Navigating to profile: {profile_url}")
                                        page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
                                        self.random_wait(3, 5)
                                        # Extract name from profile page
                                        name_el = page.query_selector('.user-profile-names .full-name, .ipsPageHeader_title, h1.username')
                                        if name_el:
                                            current_username = name_el.inner_text().strip()
                                            print(f" [Identity] Confirmed name on profile page: {current_username}")
                                        # Go back to origin
                                        page.go_back()
                                        self.random_wait(2, 3)

                            page.keyboard.press("Escape")
                        except Exception as e:
                            print(f" [Identity] Probe failed: {e}")
                    if current_username != "unknown": break
            # -----------------------------------
            
            # Display detected username for user confirmation
            if current_username != "unknown":
                print(f"\n [Identity] MY USERNAME ON THIS FORUM: {current_username}")
            else:
                print(f"\n [Identity] WARNING: Could not detect my username on this forum.")

            # Determine which posts to actually process
            # We want to process NEW posts AND threads we already replied to IF someone else has since responded.
            final_posts = []
            for post_id, full_url in post_urls:
                # Basic check: never replied? Add to list.
                if not self.has_replied(post_id, platform_name):
                    final_posts.append((post_id, full_url))
                else:
                    # Special check: Already in DB, but is there a NEW reply from someone else?
                    # We add it to 'final_posts' and the scraping logic below will handle the rest.
                    # This allows "re-visiting" threads.
                    final_posts.append((post_id, full_url))
                    # print(f"    Checking for follow-ups in: {post_id}")

            print(f" Ready to process {len(final_posts)} threads (Checking for Original Questions & Follow-ups)")
            post_urls = final_posts

            replied_count = 0
            for post_id, full_url in post_urls:
                if replied_count >= config.MAX_REPLIES_PER_SESSION:
                    break
                
                # --- NEW: PACING / ANTI-SPAM DELAY ---
                # Ensure 5-10 minutes (300-600s) have passed since the LAST successful reply
                import time
                current_time = time.time()
                elapsed = current_time - self.global_last_reply_time
                required_delay = random.randint(300, 600)  # 5-10 minutes
                
                if self.global_last_reply_time > 0 and elapsed < required_delay:
                    wait_needed = required_delay - elapsed
                    print(f" [Pacing] Waiting {int(wait_needed)}s before next reply to maintain human-like behavior...")
                    time.sleep(wait_needed)
                # ------------------------------------

                print(f" Checking post: {full_url}")
                try:
                    # Retry logic for loading post with increased timeout
                    for attempt in range(2):
                        try:
                            # Use networkidle for heavy pages like Bubble
                            page.goto(full_url, wait_until="domcontentloaded", timeout=90000)
                            self.random_wait(5, 8)
                            
                            # Verify if page actually loaded (sometimes it's a blank white screen)
                            if not page.query_selector('.topic-post, .ipsComment, .post-stream, #post_1'):
                                print(f"    Page seems empty, attempting reload...")
                                page.reload(wait_until="domcontentloaded", timeout=60000)
                                self.random_wait(5, 8)
                            break
                        except Exception as e:
                            if attempt == 1: raise e 
                            print(f"    Retry loading {full_url}...")
                            self.random_wait(5, 10)
                except Exception as e:
                    print(f" Timeout loading post {post_id}, skipping... ({str(e)[:50]})")
                    # Record as skipped to avoid infinite retry loops in future
                    self.log_interaction(platform_url, post_id, full_url, "[SKIPPED_TIMEOUT]")
                    continue

                if self.is_post_solved(page):
                    print(f" Skipping solved post: {post_id}")
                    # Record as skipped so we don't check it again
                    self.log_interaction(platform_url, post_id, full_url, "[SKIPPED_SOLVED]")
                    continue

                # 0. Load Full Thread (Scroll to bottom first)
                # This ensures we see the actual LATEST messages on lazy-loading forums (Discourse/Zoom)
                self.smart_scroll(page)
                self.random_wait(2, 4)

                # --- THREAD MEMORY SCRAPING ---
                original_question = ""
                thread_history = []
                
                # 1. Scrape Original Post (First post in thread)
                # Discourse: The first .cooked element. 
                # IPS: The first ipsType_richText.
                first_post_sel = '.topic-post:first-child .cooked, #elPostFeed .ipsComment:first-child .ipsType_richText'
                op_el = page.query_selector(first_post_sel)
                if not op_el:
                    # Fallback to the general list if first-child logic fails
                    op_el = page.query_selector('.cooked, .ipsType_richText')
                
                if op_el:
                    original_question = op_el.inner_text().strip()
                
                # 2. Scrape Recent Conversation (Last 5 messages)
                post_blocks = page.query_selector_all('.topic-post, .ipsComment, .post-stream .post-cloze')
                last_speaker = "unknown"
                
                if post_blocks:
                    # Iterate through the last few blocks to build history
                    for block in post_blocks[-5:]:
                        # Discourse: .names .username a, .names .username, .main-avatar a
                        # IPS: .ipsType_break[href*="/profile/"]
                        author_el = block.query_selector('.username a, .names .username, .ipsType_break[href*="/profile/"], .main-avatar a')
                        if author_el:
                            aria_label = author_el.get_attribute('aria-label') or ""
                            if 'profile' in aria_label.lower():
                                author_name = aria_label.split("'s")[0].strip()
                            else:
                                author_name = author_el.inner_text().strip()
                        else:
                            author_name = "unknown"
                        
                        content_el = block.query_selector('.cooked, .ipsType_richText')
                        content_text = content_el.inner_text().strip() if content_el else ""
                        
                        if content_text:
                            thread_history.append(f"{author_name}: {content_text[:300]}...")
                    
                    # Define last_block for later usage
                    last_block = post_blocks[-1]
                    
                    # Repeat for the last speaker specifically
                    last_author_el = last_block.query_selector('.username a, .names .username, .ipsType_break[href*="/profile/"], .main-avatar a')
                    if last_author_el:
                        aria_label = last_author_el.get_attribute('aria-label') or ""
                        if 'profile' in aria_label.lower():
                            last_speaker = aria_label.split("'s")[0].strip()
                        else:
                            last_speaker = last_author_el.inner_text().strip()
                    else:
                        last_speaker = "unknown"

                    # Identify Original Poster (OP) - usually the first block
                    op_author_el = post_blocks[0].query_selector('.username a, .names .username, .ipsType_break[href*="/profile/"]')
                    op_name = op_author_el.inner_text().strip() if op_author_el else "unknown"
                    print(f" [Context] OP is '{op_name}', Last speaker is '{last_speaker}'")

                    # --- ENHANCED: GLOBAL STAFF/MODERATOR DETECTION ---
                    # Check ALL posts in history for official markers
                    has_official_reply = False
                    staff_selectors = [
                        '.moderator', '.admin', '.group-staff', '.staff', 
                        '.d-icon-shield', '.fa-shield', '.fa-shield-alt', 
                        '[title*="Moderator"]', '[title*="Staff"]',
                        '.is-staff', '.is-admin'
                    ]
                    
                    for block in post_blocks:
                        for s_sel in staff_selectors:
                            if block.query_selector(s_sel):
                                has_official_reply = True
                                break
                        if has_official_reply: break
                    
                    if has_official_reply:
                        print(f" [Skipping] Official Staff/Moderator reply detected in this thread. Avoiding interference.")
                        continue
                    # ----------------------------------------------------

                # --- IGNORE SYSTEM/BOT/ADMIN USERS ---
                ignore_users = ['system', 'discobot', 'staff', 'welcome', 'bot', 'admin', 'moderator']
                if any(u == last_speaker.lower() for u in ignore_users):
                    print(f" [Skipping] Last speaker '{last_speaker}' is a system/bot account.")
                    continue
                # -------------------------------

                # 3. Decision: Should we reply?
                print(f" [Debug] Identity Check: Me={current_username}, Last Speaker={last_speaker}")
                
                # Account-level identity aliases (Email, username without domain, etc.)
                my_aliases = [current_username.lower(), "kernelcoder", "pixelpioneer", "pixelpioneer23", "peterson23"]
                if self.current_email:
                    email_prefix = self.current_email.split('@')[0].lower()
                    my_aliases.append(self.current_email.lower())
                    my_aliases.append(email_prefix)
                
                # 1. Check for "Edit" or "Delete" button on the last block - 100% proof of ownership
                edit_btn = last_block.query_selector('.edit-post, .fa-pencil-alt, button:has-text("Edit"), .ipsComment_controls li a[href*="do=edit"], .edit-button')
                if not edit_btn:
                    # Specific selectors for Zoom/Discourse variations
                    edit_btn = last_block.query_selector('.post-controls .edit, button.post-action-menu__edit, [title="edit this post"], .d-icon-pencil')
                
                is_me_speaking = False
                if edit_btn and edit_btn.is_visible():
                    is_me_speaking = True
                    print(f" [Identity] Ownership confirmed via EDIT/DELETE button visibility.")
                
                # 2. Check speaker name against ALL known aliases and email
                if not is_me_speaking:
                    if last_speaker.lower() in my_aliases:
                        is_me_speaking = True
                        print(f" [Identity] Ownership confirmed via username match: '{last_speaker}'")
                
                # 3. Visual class check (Discourse specific)
                if not is_me_speaking:
                    if last_block.query_selector('.post--by-current-user, .current-user-post'):
                        is_me_speaking = True
                        print(f" [Identity] Ownership confirmed via CSS class.")
                delete_btn = last_block.query_selector('button:has-text("Delete"), .delete-post, a[href*="delete"]')
                
                # 2. Check for "current-user" CSS classes (Discourse themes)
                is_current_user_block = last_block.evaluate("el => el.classList.contains('post--by-current-user') || el.classList.contains('current-user-post')")

                if edit_btn or delete_btn or is_current_user_block:
                    reason = "Edit button" if edit_btn else ("Delete button" if delete_btn else "Current-user CSS class")
                    print(f" [Identity] Ownership DETECTED ({reason}): last post belongs to ME.")
                    is_me_speaking = True
                
                if not is_me_speaking:
                    if current_username != "unknown" and last_speaker.lower() == current_username.lower():
                        is_me_speaking = True
                    if any(alias.lower() == last_speaker.lower() for alias in self.bot_aliases):
                        is_me_speaking = True
                
                
                # Check for mentions: If bot is mentioned in recent posts, allow follow-up
                is_mentioned = False
                if current_username != "unknown":
                    # Check if bot's name is mentioned in thread content (case insensitive)
                    thread_content_lower = ' '.join(thread_history).lower()
                    mention_patterns = [
                        f"@{current_username.lower()}",
                        current_username.lower()
                    ]
                    for pattern in mention_patterns:
                        if pattern in thread_content_lower:
                            is_mentioned = True
                            print(f" [Mention] DETECTED: I was mentioned as '{current_username}' in this thread!")
                            break
                
                # STRICT RULE: If bot has already replied to this thread, SKIP IT
                # UNLESS the bot was explicitly mentioned
                if self.has_replied(post_id, platform_name):
                    if is_mentioned:
                        print(f" [Follow-up] Someone mentioned me (@{current_username}). Proceeding with reply.")
                        # Allow follow-up when mentioned
                    else:
                        print(f" [Skipping] I have already replied to thread {post_id}. No follow-up needed.")
                        continue
                
                # Also skip if bot is currently the last speaker (self-reply prevention)
                if is_me_speaking:
                    print(f" [Skipping] Bot identity '{last_speaker}' detected as last speaker. Avoiding self-reply.")
                    # Update local memory to ensure we never check this thread again
                    self.log_interaction(platform_url, post_id, full_url, "[ALREADY_REPLIED_DETECTED]")
                    continue

                # --- NEW PRE-AI CHECK: Is the thread replyable? ---
                print(" Verifying if thread is open for replies BEFORE calling AI...")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self.random_wait(2, 3)
                self.handle_overlays(page)

                valid_reply_btn = None
                possible_buttons = page.query_selector_all('button, a.btn')
                # 1. Try to find the MAIN topic reply button first (at the bottom)
                for btn in possible_buttons:
                    if not btn.is_visible(): continue
                    classes = btn.get_attribute('class') or ''
                    text = btn.inner_text().strip().lower()
                    if (text == 'reply' or text == 'post reply') and ('topic-footer-main-buttons' in classes or 'create' in classes):
                        valid_reply_btn = btn
                        print(f" Found main topic reply button: {text}")
                        break
                
                # 2. Fallback to any visible reply button if main one not found
                if not valid_reply_btn:
                    for btn in possible_buttons:
                        if not btn.is_visible(): continue
                        text = btn.inner_text().strip().lower()
                        if text == 'reply' or text == 'post reply':
                            valid_reply_btn = btn
                            break
                
                if not valid_reply_btn and not page.query_selector('textarea[placeholder*="reply"]'):
                    print(f" [Skipping] No reply button or editor found. Thread {post_id} might be closed.")
                    self.log_interaction(platform_url, post_id, full_url, "[SKIPPED_THREAD_CLOSED]")
                    continue
                
                print(" Generating AI reply (with Targeted Context & Self-Verification)...")
                ai_reply = self.replier.generate_reply(
                    original_post=f"[{op_name} asks]: {original_question}", 
                    thread_history=thread_history, 
                    platform_name=platform_name,
                    last_speaker=last_speaker,
                    my_name=current_username
                )
                # ------------------------------
                
                ai_reply = re.sub(r'(Best regards|Sincerely|Thanks|Regards),?\s*\[?Assistant\]?.*$', '', ai_reply, flags=re.IGNORECASE | re.MULTILINE).strip()
                
                # Check for AI self-verification [SKIP]
                if "[SKIP]" in ai_reply.upper() or len(ai_reply) < 5:
                    print(f" [AI Verification] Reply skipped because AI marked it as irrelevant or insufficient: {ai_reply}")
                    self.log_interaction(platform_url, post_id, full_url, "[SKIPPED_AI_VERIFICATION_FAILED]")
                    continue
                else:
                    print(f" [AI Verification] Passed: Reply generated for '{last_speaker}'")
                
                # --- MANUAL REVIEW MODE ---
                if getattr(config, 'MANUAL_REVIEW', False):
                    print("\n" + "="*50)
                    print(f" PROPOSED REPLY FOR: {full_url}")
                    print("-" * 50)
                    print(ai_reply)
                    print("-" * 50)
                    user_input = ""
                    while user_input not in ['y', 'n', 'e']:
                        user_input = input(" Approval Required: [Y]es / [N]o to skip / [E]dit: ").lower().strip()
                    
                    if user_input == 'n':
                        print(" Skipping post as per user request.")
                        continue
                    elif user_input == 'e':
                        print(" Enter your custom reply (Press Enter twice to finish):")
                        lines = []
                        while True:
                            line = input()
                            if line == "": break
                            lines.append(line)
                        ai_reply = "\n".join(lines).strip()
                        print(" Custom reply set.")
                    else:
                        print(" Proceeding with AI reply.")
                    print("="*50 + "\n")
                # --------------------------
                
                # Initial Reply Click (Open Editor)
                # Retry loop for the actual replying process (click reply -> type -> submit)
                reply_success = False
                valid_reply_btn = None # Reset initially
                
                for reply_attempt in range(3):
                    # ALWAYS Refresh the button reference at the start of an attempt
                    valid_reply_btn = None 

                    if reply_attempt > 0:
                        print(f" [Retry] Attempt {reply_attempt+1}/3: Reloading and re-verifying...")
                        try:
                            page.reload(wait_until="domcontentloaded", timeout=60000)
                            self.random_wait(5, 8)
                            self.handle_overlays(page)
                            # Re-scroll after reload to find buttons
                            self.smart_scroll(page)
                            
                            # CRITICAL: Pre-retry check. Did the previous attempt actually succeed?
                            # This prevents double-posting if verification was just too impatient.
                            if self.verify_post_on_page(page, current_username, ai_reply):
                                print(f" [OK] Post found on page AFTER reload. Skipping retry for {post_id}.")
                                self.log_interaction(platform_name, post_id, full_url, ai_reply)
                                self.global_last_reply_time = time.time() # Mark time of success
                                replied_count += 1
                                reply_success = True
                                break
                        except: pass

                    # Proactively clear overlays before searching for buttons
                    self.handle_overlays(page)
    
                    reply_btn = None
                    
                    # Strategy: Search for robust "Reply" buttons
                    # Exclude buttons that look like counts (e.g. "1 Reply")
                    print(" Looking for topic-level Reply button...")
                    
                    # If button went stale or not found yet, find it again using prioritized search
                    if not valid_reply_btn:
                        possible_buttons = page.query_selector_all('button, a.btn')
                        # Priority 1: Main Topic Footer Button
                        for btn in possible_buttons:
                            if not btn.is_visible(): continue
                            classes = btn.get_attribute('class') or ''
                            text = btn.inner_text().strip().lower()
                            if (text == 'reply' or text == 'post reply') and ('topic-footer-main-buttons' in classes or 'create' in classes):
                                valid_reply_btn = btn
                                break
                        # Priority 2: Any Reply Button
                        if not valid_reply_btn:
                            for btn in possible_buttons:
                                if not btn.is_visible(): continue
                                text = btn.inner_text().strip().lower()
                                if text == 'reply' or text == 'post reply':
                                    valid_reply_btn = btn
                                    break

                    if not valid_reply_btn:
                         valid_reply_btn = page.query_selector(
                            '.topic-footer-main-buttons button.create, '
                            '#topic-footer-buttons button.create, '
                            'button.btn-primary:has-text("Reply"), '
                            '[component="topic/reply"], '
                            '.ipsButton_primary:has-text("Reply")'
                        )

                    if valid_reply_btn:
                        try:
                            btn_text = valid_reply_btn.inner_text().strip()
                            print(f" Found Topic Reply button, clicking... (Text: '{btn_text}')")
                        except Exception as e:
                            print(f" [Warning] Button became stale just now ({e}), searching one last time...")
                            # A simple rescue search
                            valid_reply_btn = page.query_selector('button.create, button:has-text("Reply")')
                            if not valid_reply_btn:
                                print(" [Error] Button lost and cannot be recovered.")
                                continue
                            print(" [Success] Recovered button.")
                        try:
                            valid_reply_btn.click(timeout=3000)
                        except:
                            valid_reply_btn.evaluate("el => el.click()")
                        self.random_wait(3, 5)
                        
                        # Wait for editor to appear with longer timeout
                        print(" Looking for editor/textarea...")
                        editor = None
                        editor_selectors = [
                            '.d-editor-input', 'textarea.d-editor-input', 
                            'textarea[aria-label*="Type here"]', '.composer-fields textarea',
                            '#reply-control textarea', '.ipsEditor_textArea'
                        ]
                        for i in range(10):
                            for sel in editor_selectors:
                                editor = page.query_selector(sel)
                                if editor and editor.is_visible(): break
                            if editor: break
                            self.random_wait(1, 2)
                        
                        submit_btn = None 
                        
                        if editor:
                            print(" Editor found. Typing reply...")
                            editor.focus()
                            self.random_wait(1, 2)
                            self.human_type(editor, ai_reply)
                            self.random_wait(2, 4)
                            
                            # Proactively clear overlays again before clicking submit
                            self.handle_overlays(page)
    
                            # Wait for Reply button to appear and become enabled
                            print("[s] Looking for the Publish/Reply button (Strictly inside Composer)...")
                            submit_btn = None
                            for attempt in range(10):
                                # STRICTLY Target the Reply button within the editor/composer area
                                reply_selector = (
                                    '#reply-control .save-or-cancel button.create:not([disabled]), '
                                    '#reply-control button.btn-primary.create:not([disabled]), '
                                    '.d-editor-footer .save-or-cancel button.create:not([disabled]), '
                                    '.composer-container .save-or-cancel button.create:not([disabled]), '
                                    '[component="topic/reply"]:not([disabled]), ' # NodeBB
                                    '[component="post/reply"]:not([disabled]), ' # NodeBB
                                    'button.ipsButton_primary:has-text("Reply"), ' # IPS
                                    'button.ipsButton_primary:has-text("Submit Reply"), '
                                    # Fallback but still scoped
                                    '#reply-control button:has-text("Reply"):not([disabled])'
                                )
                                submit_btn = page.query_selector(reply_selector)
                                
                                if submit_btn:
                                    if submit_btn.is_visible() and submit_btn.is_enabled():
                                        print(f"[v] Found visible and enabled button with selector: {reply_selector[:50]}...")
                                        break
                                    else:
                                        print(f" Found button but not yet ready (visible: {submit_btn.is_visible()}, enabled: {submit_btn.is_enabled()})")
                            else:
                                if attempt == 5: # Halfway through, debug info
                                    print("[s] Debug: Composer button not found. Checking if editor is open...")
                                    
                                if attempt % 3 == 0:
                                    print(f"  ... still searching for button (attempt {attempt+1}/10)")
                            
                            self.random_wait(1, 2)
                        
                        if submit_btn:
                            print("[>] Clicking Reply button (Composer)...")
                            try:
                                # Ensure it's in view before clicking
                                submit_btn.scroll_into_view_if_needed()
                                self.random_wait(0.5, 1)
                                submit_btn.click(timeout=5000)
                                print("[v] Reply button clicked successfully")
                            except Exception as e:
                                print(f"[v] Normal click failed ({e}), trying force click...")
                                try:
                                    submit_btn.click(force=True)
                                    print("[v] Force click successful")
                                except Exception as e2:
                                    print(f"[!] Force click failed ({e2}), using keyboard shortcut...")
                                    page.keyboard.press("Control+Enter")
                        else:
                            # Fallback: Use keyboard shortcut (Ctrl+Enter is common for submit)
                            print("[!] Reply button not found after waiting, trying Ctrl+Enter...")
                            page.keyboard.press("Control+Enter")
                        
                        # Wait longer to ensure submission completes
                        print("[...] Waiting for reply to be posted & verifying on page...")
                        self.random_wait(8, 15) # Give it more time for database sync
                        
                        # 2. Check if editor is gone
                        editor_still_there = page.query_selector('.d-editor-input, textarea.d-editor-input, .ipsEditor_textArea')
                        
                        # 3. Explicit Verification
                        if self.verify_post_on_page(page, current_username, ai_reply):
                            print(f"[OK] Reply POSITIVELY verified on page for {post_id}")
                            self.log_interaction(platform_name, post_id, full_url, ai_reply)
                            self.global_last_reply_time = time.time() # Mark success for pacing
                            replied_count += 1
                            reply_success = True
                            break
                        elif not editor_still_there:
                            print(f"[!] False Positive Warning: Editor closed but post NOT found for {post_id}")
                        else:
                            print(f"[!] Reply NOT found on page for {post_id}. Editor still visible.")
                            # Final Hail Mary: JS Click
                            if submit_btn:
                                print("[!] Attempting final Javascript click...")
                                submit_btn.evaluate("el => el.click()")
                                self.random_wait(3, 5)
                                if not page.query_selector('.d-editor-input'):
                                    print(f"[OK] Reply successfully posted (after JS click) for {post_id}")
                                    self.log_interaction(platform_name, post_id, full_url, ai_reply)
                                    self.global_last_reply_time = time.time() # Mark success for pacing
                                    replied_count += 1
                                    reply_success = True
                                    break
                    
                    if not reply_success:
                         print(f" [X] Reply attempt {reply_attempt+1} failed (Editor not found or submit failed).")
                
                if not reply_success:
                    print(f" [X] Failed to reply to {full_url} after 3 attempts.")
                
            context.close()
            print(f"[DONE] Finished processing {platform_name}")


