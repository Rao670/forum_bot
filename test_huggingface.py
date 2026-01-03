from huggingface_bot import HuggingFaceBot
import time

def main():
    bot = HuggingFaceBot()
    
    # List of forums to process (add any Discourse-based forum URL here)
    forums = [
        {'url': 'http://discourse.webflow.com/', 'name': 'Webflow Forums'},
        # {'url': 'https://forum.bubble.io/', 'name': 'Bubble.io Forums'},
        # Add more forums here:
        # {'url': 'https://discuss.huggingface.co/', 'name': 'HuggingFace Forums'},
        # {'url': 'https://forum.example.com/', 'name': 'Example Forum'},
    ]
    
    print("--- Forum Bot Started ---")
    
    for forum in forums:
        print(f"\n{'='*60}")
        print(f"Processing: {forum['name']}")
        print(f"URL: {forum['url']}")
        print(f"{'='*60}\n")
        
        try:
            bot.run_huggingface_task(forum['url'])
        except Exception as e:
            print(f"❌ Error processing {forum['name']}: {e}")
            import traceback
            traceback.print_exc()
        
        # Wait between forums
        if forum != forums[-1]:  # Don't wait after last forum
            print(f"\n⏳ Waiting before next forum...")
            time.sleep(30)
    
    print("\n" + "="*60)
    print("--- All tasks completed! ---")
    print(f"📄 Check reply history in: bubble_reply_history.txt")
    print(f"💾 Database: bot_data.db")
    print("="*60)

if __name__ == "__main__":
    main()

