# scripts/start_all.py
import os
import sys
import time
import subprocess

def start_bot(bot_folder):
    """Start a bot in background"""
    bot_path = os.path.join('bots', bot_folder)
    app_file = os.path.join(bot_path, 'app.py')
    
    if not os.path.exists(app_file):
        print(f"❌ app.py not found in {bot_path}")
        return None
    
    print(f"🚀 Starting {bot_folder}...")
    
    # Install dependencies
    req_file = os.path.join(bot_path, 'requirements.txt')
    if os.path.exists(req_file):
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], 
                     capture_output=True)
    
    # Start bot
    log_file = os.path.join('logs', f'{bot_folder}.log')
    
    with open(log_file, 'a') as log:
        process = subprocess.Popen(
            [sys.executable, app_file],
            cwd=bot_path,
            stdout=log,
            stderr=log,
            text=True
        )
    
    print(f"✅ {bot_folder} started (PID: {process.pid})")
    return process

def main():
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Start all bots
    bots = ['bot1', 'bot2', 'bot3']
    processes = []
    
    for bot in bots:
        proc = start_bot(bot)
        if proc:
            processes.append(proc)
        time.sleep(2)
    
    print(f"\n✅ All bots started! Total: {len(processes)}")
    print("Bots are running in background")
    print("Logs are in 'logs/' directory")
    
    # Keep script running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping all bots...")
        for proc in processes:
            proc.terminate()

if __name__ == "__main__":
    main()