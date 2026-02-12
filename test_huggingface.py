import os
import time
import random
from huggingface_bot import HuggingFaceBot

def main():
    bot = HuggingFaceBot()
    urls_file = 'urls.txt'
    
    if not os.path.exists(urls_file):
        print(f"Error: {urls_file} not found. Please create it and add forum URLs (one per line).")
        return

    with open(urls_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    if not urls:
        print(f"Warning: No URLs found in {urls_file}.")
        return

    print("--- Forum Bot Started ---")
    print(f"Found {len(urls)} forums to process.")
    
    # Shuffle URLs to avoid fixed pattern
    random.shuffle(urls)
    
    for url in urls:
        # --- RANDOM SKIP LOGIC ---
        # 30% chance to skip a forum entirely this run to mimic human randomness
        if random.random() < 0.3:
            print(f"\n [Randomness] Skipping {url} this session to mimic human behavior.")
            continue
            
        # Simple name extraction from URL
        name = url.split('//')[-1].split('/')[0].replace('www.', '')
        
        print(f"\n{'='*60}")
        print(f"Processing: {name}")
        print(f"URL: {url}")
        print(f"{'='*60}\n")
        
        try:
            bot.run_huggingface_task(url)
        except Exception as e:
            print(f"Error processing {name}: {e}")
            import traceback
            traceback.print_exc()
        
        # Wait between forums (Randomized 1-3 minutes)
        if url != urls[-1]:
            wait_time = random.randint(60, 180)
            print(f"\nWaiting {wait_time}s before next forum...")
            time.sleep(wait_time)
    
    print("\n" + "="*60)
    print("--- All tasks completed! ---")
    print(f" Check reply history in: bubble_reply_history.txt")
    print(f" Database: bot_data.db")
    print("="*60)

if __name__ == "__main__":
    main()
