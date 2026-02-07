# scripts/keep_alive.py
import requests
import time
import threading
import os

# UptimeRobot or similar ping service
PING_URLS = [
    "https://telegram-bots-manager.onrender.com/health",
    "https://api.render.com/deploy/srv-xxx/health"  # Your Render URL
]

def ping_services():
    """Ping services to keep them alive"""
    while True:
        for url in PING_URLS:
            try:
                response = requests.get(url, timeout=10)
                print(f"✅ Pinged {url}: {response.status_code}")
            except Exception as e:
                print(f"❌ Failed to ping {url}: {e}")
        time.sleep(300)  # Ping every 5 minutes

if __name__ == "__main__":
    print("🚀 Starting keep-alive service...")
    threading.Thread(target=ping_services, daemon=True).start()
    
    # Keep main thread alive
    while True:
        time.sleep(1)