from bot_core import AutomationBot
import time

def main():
    bot = AutomationBot()
    
    # List of platforms to process
    platforms = [
        {'url': 'https://forums.ea.com/', 'name': 'EA Forums'},
        # Aap yahan mazeed platforms add kar sakte hain:
        # {'url': 'https://www.odoo.com/forum/help-1', 'name': 'Odoo Forum'},
    ]
    
    print("--- Community Automation Bot Started ---")
    
    for platform in platforms:
        print(f"\nProcessing {platform['name']}...")
        try:
            # Ye function platform par jayega aur replies dega
            bot.run_platform_task(platform['url'], platform['name'])
        except Exception as e:
            print(f"Error processing {platform['name']}: {e}")
        
        # Platforms ke darmiyan thora break
        print("Waiting before next platform...")
        time.sleep(30)

    print("\n--- All tasks completed! ---")

if __name__ == "__main__":
    main()
