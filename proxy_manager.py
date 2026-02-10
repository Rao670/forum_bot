import requests
import re
import random

class ProxyManager:
    def __init__(self):
        self.proxy_list = []
        self.api_url = "https://free-proxy-list.net/"

    def fetch_proxies(self):
        """
        Scrapes free-proxy-list.net for fresh HTTPS proxies.
        """
        print("🌐 Fetching fresh proxies from free-proxy-list.net...")
        try:
            response = requests.get(self.api_url, timeout=10)
            if response.status_code == 200:
                # Find all IP:Port pairs in the table
                matches = re.findall(r'\d+\.\d+\.\d+\.\d+:\d+', response.text)
                if not matches:
                    # Alternative regex if they are separated in columns
                    ips = re.findall(r'<td>(\d+\.\d+\.\d+\.\d+)</td>', response.text)
                    ports = re.findall(r'<td>(\d+)</td>', response.text)
                    matches = [f"{ips[i]}:{ports[i]}" for i in range(min(len(ips), len(ports)))]
                
                self.proxy_list = matches
                print(f"✅ Found {len(self.proxy_list)} potential proxies.")
                return True
        except Exception as e:
            print(f"❌ Error fetching proxies: {e}")
        return False

    def get_random_proxy(self):
        """
        Returns a random proxy string formatted for Playwright.
        """
        if not self.proxy_list:
            if not self.fetch_proxies():
                return None
        
        if self.proxy_list:
            proxy = random.choice(self.proxy_list)
            # Playwright format: http://ip:port
            return f"http://{proxy}"
        return None

if __name__ == "__main__":
    # Test the manager
    pm = ProxyManager()
    p = pm.get_random_proxy()
    print(f"Selected Proxy: {p}")
