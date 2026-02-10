import os
import time
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
    
    for url in urls:
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
        
        # Wait between forums
        if url != urls[-1]:
            print(f"\nWaiting before next forum...")
            time.sleep(30)
    
    print("\n" + "="*60)
    print("--- All tasks completed! ---")
    print(f" Check reply history in: bubble_reply_history.txt")
    print(f" Database: bot_data.db")
    print("="*60)

if __name__ == "__main__":
    main()
