# manager/main.py
import os
import sys
import time
import logging
import subprocess
import threading
from flask import Flask, jsonify
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app for web interface
app = Flask(__name__)

# Bot configurations
BOTS = [
    {
        "name": "Telegram Bot 1",
        "folder": "bots/bot1",
        "port": 5001,
        "status": "stopped",
        "pid": None,
        "log_file": "logs/bot1.log"
    },
    {
        "name": "Telegram Bot 2", 
        "folder": "bots/bot2",
        "port": 5002,
        "status": "stopped",
        "pid": None,
        "log_file": "logs/bot2.log"
    },
    {
        "name": "Telegram Bot 3",
        "folder": "bots/bot3", 
        "port": 5003,
        "status": "stopped",
        "pid": None,
        "log_file": "logs/bot3.log"
    }
]

class BotManager:
    def __init__(self):
        self.processes = {}
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Create logs directory
        self.logs_dir = os.path.join(self.base_dir, 'logs')
        os.makedirs(self.logs_dir, exist_ok=True)
        
        logger.info(f"🤖 Bot Manager Initialized")
        logger.info(f"Base Directory: {self.base_dir}")
        logger.info(f"Logs Directory: {self.logs_dir}")
    
    def install_dependencies(self, bot_folder):
        """Install bot dependencies"""
        req_file = os.path.join(self.base_dir, bot_folder, 'requirements.txt')
        
        if os.path.exists(req_file):
            logger.info(f"Installing dependencies for {bot_folder}...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_file],
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"Dependencies installed for {bot_folder}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install dependencies for {bot_folder}: {e}")
    
    def start_bot(self, bot_info):
        """Start a single bot"""
        bot_name = bot_info["name"]
        bot_folder = os.path.join(self.base_dir, bot_info["folder"])
        log_file = os.path.join(self.base_dir, bot_info["log_file"])
        
        if not os.path.exists(bot_folder):
            logger.error(f"Bot folder not found: {bot_folder}")
            return False
        
        app_file = os.path.join(bot_folder, 'app.py')
        if not os.path.exists(app_file):
            logger.error(f"app.py not found in {bot_folder}")
            return False
        
        # Install dependencies
        self.install_dependencies(bot_info["folder"])
        
        try:
            # Open log file
            log_fd = open(log_file, 'a', buffering=1)
            log_fd.write(f"\n{'='*60}\n")
            log_fd.write(f"Bot started at {datetime.now()}\n")
            log_fd.write(f"{'='*60}\n")
            
            # Start bot process
            process = subprocess.Popen(
                [sys.executable, app_file],
                cwd=bot_folder,
                stdout=log_fd,
                stderr=log_fd,
                text=True,
                bufsize=1
            )
            
            # Store process info
            bot_info["pid"] = process.pid
            bot_info["process"] = process
            bot_info["log_fd"] = log_fd
            bot_info["status"] = "running"
            bot_info["start_time"] = datetime.now()
            
            self.processes[bot_name] = bot_info
            
            logger.info(f"✅ Started {bot_name} (PID: {process.pid})")
            
            # Monitor process
            threading.Thread(
                target=self.monitor_bot,
                args=(bot_name, process),
                daemon=True
            ).start()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start {bot_name}: {e}")
            return False
    
    def monitor_bot(self, bot_name, process):
        """Monitor bot process"""
        while True:
            if process.poll() is not None:
                logger.warning(f"❌ {bot_name} stopped with code {process.returncode}")
                if bot_name in self.processes:
                    self.processes[bot_name]["status"] = "stopped"
                
                # Auto-restart after 10 seconds
                time.sleep(10)
                logger.info(f"🔄 Attempting to restart {bot_name}...")
                
                # Find bot config
                for bot in BOTS:
                    if bot["name"] == bot_name:
                        self.start_bot(bot)
                        break
                break
            time.sleep(5)
    
    def start_all_bots(self):
        """Start all bots"""
        logger.info("🚀 Starting all bots...")
        
        for bot in BOTS:
            self.start_bot(bot)
            time.sleep(2)  # Stagger starts
    
    def stop_bot(self, bot_name):
        """Stop a specific bot"""
        if bot_name in self.processes:
            bot_info = self.processes[bot_name]
            process = bot_info["process"]
            
            logger.info(f"🛑 Stopping {bot_name} (PID: {process.pid})...")
            
            process.terminate()
            try:
                process.wait(timeout=5)
                logger.info(f"✅ {bot_name} stopped gracefully")
            except:
                process.kill()
                logger.warning(f"⚠️ {bot_name} force killed")
            
            # Close log file
            if bot_info.get("log_fd"):
                bot_info["log_fd"].close()
            
            bot_info["status"] = "stopped"
            del self.processes[bot_name]
    
    def stop_all_bots(self):
        """Stop all bots"""
        logger.info("🛑 Stopping all bots...")
        for bot_name in list(self.processes.keys()):
            self.stop_bot(bot_name)
    
    def get_status(self):
        """Get status of all bots"""
        status = []
        current_time = datetime.now()
        
        for bot in BOTS:
            bot_status = {
                "name": bot["name"],
                "folder": bot["folder"],
                "status": bot["status"],
                "pid": bot.get("pid")
            }
            
            if bot["name"] in self.processes:
                bot_info = self.processes[bot["name"]]
                if bot_info["process"].poll() is None:
                    # Calculate uptime
                    uptime = current_time - bot_info["start_time"]
                    hours, remainder = divmod(uptime.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    bot_status.update({
                        "uptime": f"{hours}h {minutes}m {seconds}s",
                        "running": True
                    })
                else:
                    bot_status["running"] = False
            else:
                bot_status["running"] = False
            
            status.append(bot_status)
        
        return status

# Create bot manager instance
bot_manager = BotManager()

# Flask Routes
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Telegram Bots Manager</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .container { background: #f5f5f5; padding: 20px; border-radius: 10px; }
            .bot-card { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .status-running { color: green; font-weight: bold; }
            .status-stopped { color: red; font-weight: bold; }
            .btn { padding: 8px 15px; margin: 5px; border: none; border-radius: 4px; cursor: pointer; }
            .btn-start { background: #4CAF50; color: white; }
            .btn-stop { background: #f44336; color: white; }
            .btn-restart { background: #ff9800; color: white; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Telegram Bots Manager</h1>
            <p>Manage your Telegram bots on Render.com</p>
            
            <div id="bots-container">
                <!-- Bots will be loaded here by JavaScript -->
            </div>
            
            <div style="margin-top: 20px;">
                <button class="btn btn-start" onclick="startAll()">Start All Bots</button>
                <button class="btn btn-stop" onclick="stopAll()">Stop All Bots</button>
                <button class="btn btn-restart" onclick="restartAll()">Restart All</button>
            </div>
        </div>
        
        <script>
            function loadBots() {
                fetch('/api/status')
                    .then(response => response.json())
                    .then(data => {
                        const container = document.getElementById('bots-container');
                        container.innerHTML = '';
                        
                        data.bots.forEach(bot => {
                            const card = document.createElement('div');
                            card.className = 'bot-card';
                            card.innerHTML = `
                                <h3>${bot.name}</h3>
                                <p>Status: <span class="status-${bot.running ? 'running' : 'stopped'}">
                                    ${bot.running ? '✅ RUNNING' : '❌ STOPPED'}
                                </span></p>
                                ${bot.running ? `<p>Uptime: ${bot.uptime}</p>` : ''}
                                <p>PID: ${bot.pid || 'N/A'}</p>
                                <p>Folder: ${bot.folder}</p>
                                <div>
                                    ${!bot.running ? 
                                        `<button class="btn btn-start" onclick="startBot('${bot.name}')">Start</button>` : 
                                        `<button class="btn btn-stop" onclick="stopBot('${bot.name}')">Stop</button>`
                                    }
                                    <button class="btn btn-restart" onclick="restartBot('${bot.name}')">Restart</button>
                                </div>
                            `;
                            container.appendChild(card);
                        });
                    });
            }
            
            function startBot(botName) {
                fetch(`/api/start/${encodeURIComponent(botName)}`, { method: 'POST' })
                    .then(() => {
                        setTimeout(loadBots, 1000);
                    });
            }
            
            function stopBot(botName) {
                fetch(`/api/stop/${encodeURIComponent(botName)}`, { method: 'POST' })
                    .then(() => {
                        setTimeout(loadBots, 1000);
                    });
            }
            
            function restartBot(botName) {
                fetch(`/api/restart/${encodeURIComponent(botName)}`, { method: 'POST' })
                    .then(() => {
                        setTimeout(loadBots, 1000);
                    });
            }
            
            function startAll() {
                fetch('/api/start-all', { method: 'POST' })
                    .then(() => {
                        setTimeout(loadBots, 2000);
                    });
            }
            
            function stopAll() {
                fetch('/api/stop-all', { method: 'POST' })
                    .then(() => {
                        setTimeout(loadBots, 2000);
                    });
            }
            
            function restartAll() {
                fetch('/api/restart-all', { method: 'POST' })
                    .then(() => {
                        setTimeout(loadBots, 2000);
                    });
            }
            
            // Load bots on page load
            document.addEventListener('DOMContentLoaded', loadBots);
            // Refresh every 10 seconds
            setInterval(loadBots, 10000);
        </script>
    </body>
    </html>
    """

@app.route('/api/status')
def api_status():
    status = bot_manager.get_status()
    return jsonify({
        "success": True,
        "bots": status,
        "total": len(status),
        "running": sum(1 for bot in status if bot.get("running", False))
    })

@app.route('/api/start/<bot_name>', methods=['POST'])
def api_start_bot(bot_name):
    for bot in BOTS:
        if bot["name"] == bot_name:
            success = bot_manager.start_bot(bot)
            return jsonify({"success": success, "message": f"Started {bot_name}"})
    return jsonify({"success": False, "message": "Bot not found"}), 404

@app.route('/api/stop/<bot_name>', methods=['POST'])
def api_stop_bot(bot_name):
    bot_manager.stop_bot(bot_name)
    return jsonify({"success": True, "message": f"Stopped {bot_name}"})

@app.route('/api/restart/<bot_name>', methods=['POST'])
def api_restart_bot(bot_name):
    bot_manager.stop_bot(bot_name)
    time.sleep(2)
    for bot in BOTS:
        if bot["name"] == bot_name:
            bot_manager.start_bot(bot)
            return jsonify({"success": True, "message": f"Restarted {bot_name}"})
    return jsonify({"success": False, "message": "Bot not found"}), 404

@app.route('/api/start-all', methods=['POST'])
def api_start_all():
    bot_manager.start_all_bots()
    return jsonify({"success": True, "message": "Starting all bots"})

@app.route('/api/stop-all', methods=['POST'])
def api_stop_all():
    bot_manager.stop_all_bots()
    return jsonify({"success": True, "message": "Stopped all bots"})

@app.route('/api/restart-all', methods=['POST'])
def api_restart_all():
    bot_manager.stop_all_bots()
    time.sleep(3)
    bot_manager.start_all_bots()
    return jsonify({"success": True, "message": "Restarted all bots"})

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

def main():
    """Main function to start everything"""
    port = int(os.environ.get("PORT", 10000))
    
    # Start all bots on startup
    logger.info("Starting all bots on startup...")
    bot_manager.start_all_bots()
    
    # Start Flask web server
    logger.info(f"Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()