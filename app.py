# app_bot_runner_no_restart.py
import os
import sys
import re
import time
import logging
import subprocess
import threading
from datetime import datetime
from flask import Flask, jsonify

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_DIR = os.getcwd()
BOTS_DIR = os.path.join(BASE_DIR, "bots")

class SimpleBotRunner:
    def __init__(self):
        self.processes = {}
        self.bots = []
        self.logs_dir = os.path.join(BASE_DIR, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Scan for bots
        self.scan_bots()
    
    def scan_bots(self):
        """Scan for app.py files in bots directory"""
        logger.info("🔍 Scanning for app.py files...")
        
        if not os.path.exists(BOTS_DIR):
            logger.warning(f"⚠️  Bots directory not found: {BOTS_DIR}")
            logger.info(f"Creating directory: {BOTS_DIR}")
            os.makedirs(BOTS_DIR, exist_ok=True)
            
            # Create example structure
            for i in range(1, 4):
                bot_dir = os.path.join(BOTS_DIR, f"bot{i}")
                os.makedirs(bot_dir, exist_ok=True)
                
                app_file = os.path.join(bot_dir, "app.py")
                with open(app_file, 'w') as f:
                    f.write(f"# Bot {i} - app.py\nprint('Bot {i} started')\n")
                
                logger.info(f"📝 Created: bots/bot{i}/app.py")
            
            return
        
        # Scan all subdirectories
        for item in os.listdir(BOTS_DIR):
            bot_path = os.path.join(BOTS_DIR, item)
            
            if os.path.isdir(bot_path):
                app_file = os.path.join(bot_path, "app.py")
                
                if os.path.exists(app_file):
                    bot_info = self.create_bot_info(bot_path, app_file)
                    if bot_info:
                        self.bots.append(bot_info)
                        logger.info(f"✅ Found: {bot_info['name']}")
                else:
                    logger.info(f"📁 {item}: No app.py (ignoring)")
        
        logger.info(f"📊 Total app.py files found: {len(self.bots)}")
    
    def create_bot_info(self, bot_path, app_file):
        """Create bot information dictionary"""
        try:
            with open(app_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            file_size = os.path.getsize(app_file)
            lines = content.count('\n') + 1
            
            # Simple type detection
            content_lower = content.lower()
            if any(x in content_lower for x in ['telebot', 'telegram', 'bot.polling']):
                bot_type = "telegram"
            elif any(x in content_lower for x in ['socket.', '.connect(', '.bind(']):
                bot_type = "tcp"
            else:
                bot_type = "generic"
            
            folder_name = os.path.basename(bot_path)
            
            return {
                "id": f"{folder_name}_{int(time.time())}",
                "name": f"Bot: {folder_name}",
                "display_name": folder_name,
                "folder": bot_path,
                "file": "app.py",
                "full_path": app_file,
                "type": bot_type,
                "status": "stopped",
                "pid": None,
                "log_file": os.path.join(self.logs_dir, f"{folder_name}.log"),
                "file_size": file_size,
                "lines": lines,
                "has_requirements": os.path.exists(os.path.join(bot_path, "requirements.txt")),
                "start_time": None,
                "exit_code": None
            }
            
        except Exception as e:
            logger.error(f"❌ Error reading {app_file}: {e}")
            return None
    
    def install_dependencies(self, bot_info):
        """Install requirements.txt if exists"""
        req_file = os.path.join(bot_info["folder"], "requirements.txt")
        
        if os.path.exists(req_file):
            logger.info(f"📦 Installing dependencies for {bot_info['name']}...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"],
                    check=False,
                    capture_output=True,
                    timeout=30
                )
            except:
                pass
    
    def start_bot(self, bot_info):
        """Start a single bot - NO AUTO RESTART"""
        bot_name = bot_info["name"]
        
        logger.info(f"🚀 Starting {bot_name}...")
        
        # Check if already running
        if bot_info["id"] in self.processes:
            process_info = self.processes[bot_info["id"]]
            if process_info["process"].poll() is None:
                logger.info(f"⚠️  {bot_name} is already running (PID: {process_info['pid']})")
                return True
        
        # Install dependencies
        self.install_dependencies(bot_info)
        
        try:
            # Open log file
            log_fd = open(bot_info["log_file"], 'a', buffering=1)
            log_fd.write(f"\n{'='*60}\n")
            log_fd.write(f"Bot started at {datetime.now()}\n")
            log_fd.write(f"Command: cd {bot_info['folder']} && python app.py\n")
            log_fd.write(f"{'='*60}\n")
            
            # Start the bot - DIRECT execution
            process = subprocess.Popen(
                [sys.executable, "app.py"],
                cwd=bot_info["folder"],
                stdout=log_fd,
                stderr=log_fd,
                text=True,
                bufsize=1
            )
            
            # Update bot info
            bot_info["pid"] = process.pid
            bot_info["status"] = "running"
            bot_info["start_time"] = datetime.now()
            bot_info["log_fd"] = log_fd
            bot_info["exit_code"] = None
            
            # Store process info
            self.processes[bot_info["id"]] = {
                "process": process,
                "bot_info": bot_info,
                "log_fd": log_fd
            }
            
            logger.info(f"✅ {bot_name} started! PID: {process.pid}")
            
            # Monitor for exit (but NO auto-restart)
            threading.Thread(
                target=self._monitor_bot_exit,
                args=(bot_info["id"], process),
                daemon=True
            ).start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start {bot_name}: {e}")
            return False
    
    def _monitor_bot_exit(self, bot_id, process):
        """Monitor bot exit - NO AUTO RESTART"""
        # Wait for process to finish
        exit_code = process.wait()
        
        # Update status
        if bot_id in self.processes:
            bot_info = self.processes[bot_id]["bot_info"]
            bot_info["status"] = "stopped"
            bot_info["exit_code"] = exit_code
            
            # Close log file
            if self.processes[bot_id].get("log_fd"):
                self.processes[bot_id]["log_fd"].close()
            
            logger.info(f"📊 {bot_info['name']} stopped with exit code: {exit_code}")
            
            # Remove from processes dict
            del self.processes[bot_id]
    
    def stop_bot(self, bot_id):
        """Stop a running bot"""
        if bot_id in self.processes:
            process_info = self.processes[bot_id]
            bot_info = process_info["bot_info"]
            
            logger.info(f"🛑 Stopping {bot_info['name']} (PID: {bot_info['pid']})...")
            
            # Terminate process
            process_info["process"].terminate()
            
            try:
                # Wait for graceful shutdown
                process_info["process"].wait(timeout=5)
                logger.info(f"✅ {bot_info['name']} stopped gracefully")
            except:
                # Force kill if not responding
                process_info["process"].kill()
                logger.warning(f"⚠️  {bot_info['name']} force killed")
            
            # Close log file
            if process_info.get("log_fd"):
                process_info["log_fd"].close()
            
            # Update bot info
            bot_info["status"] = "stopped"
            bot_info["exit_code"] = process_info["process"].returncode
            
            # Remove from processes
            del self.processes[bot_id]
            
            return True
        
        return False
    
    def start_all_bots(self):
        """Start all bots"""
        logger.info("="*60)
        logger.info("🚀 STARTING ALL BOTS (NO AUTO-RESTART)")
        logger.info("="*60)
        
        success_count = 0
        
        for bot in self.bots:
            if self.start_bot(bot):
                success_count += 1
            time.sleep(1)  # Small delay
        
        logger.info(f"✅ Started {success_count}/{len(self.bots)} bots")
        logger.info("⚠️  Note: Bots will NOT auto-restart on crash")
    
    def stop_all_bots(self):
        """Stop all running bots"""
        logger.info("🛑 Stopping all bots...")
        
        for bot_id in list(self.processes.keys()):
            self.stop_bot(bot_id)
        
        logger.info("✅ All bots stopped")
    
    def get_status(self):
        """Get current status of all bots"""
        status_list = []
        current_time = datetime.now()
        
        for bot in self.bots:
            bot_status = {
                "id": bot["id"],
                "name": bot["name"],
                "display_name": bot["display_name"],
                "type": bot["type"],
                "status": bot["status"],
                "running": False,
                "pid": bot.get("pid"),
                "folder": bot["display_name"],
                "file_size": bot["file_size"],
                "lines": bot["lines"],
                "has_requirements": bot["has_requirements"]
            }
            
            # Check if running
            if bot["id"] in self.processes:
                process = self.processes[bot["id"]]["process"]
                if process.poll() is None:  # Still running
                    bot_status["running"] = True
                    
                    # Calculate uptime
                    if bot.get("start_time"):
                        uptime = current_time - bot["start_time"]
                        hours, rem = divmod(uptime.seconds, 3600)
                        mins, secs = divmod(rem, 60)
                        bot_status["uptime"] = f"{hours}h {mins}m {secs}s"
                else:
                    # Process finished but not cleaned up yet
                    bot_status["exit_code"] = process.returncode
            
            status_list.append(bot_status)
        
        return status_list

# Create runner instance
runner = SimpleBotRunner()

# Flask Routes
@app.route('/')
def home():
    status = runner.get_status()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 Simple Bot Runner</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f0f2f5; }
            .container { max-width: 1000px; margin: 0 auto; }
            header { text-align: center; padding: 20px 0; }
            .dashboard { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }
            .stat-card { background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }
            .stat-number { font-size: 1.8em; font-weight: bold; }
            .controls { text-align: center; margin: 20px 0; }
            .btn { padding: 10px 20px; margin: 0 5px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
            .btn-start { background: #4CAF50; color: white; }
            .btn-stop { background: #f44336; color: white; }
            .btn-rescan { background: #2196F3; color: white; }
            .bots-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            .bots-table th, .bots-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            .bots-table th { background: #f8f9fa; }
            .status-badge { padding: 4px 8px; border-radius: 12px; font-size: 0.8em; color: white; }
            .status-running { background: #4CAF50; }
            .status-stopped { background: #f44336; }
            .type-badge { padding: 3px 8px; border-radius: 10px; font-size: 0.7em; color: white; }
            .type-telegram { background: #2196F3; }
            .type-tcp { background: #FF9800; }
            .type-generic { background: #9E9E9E; }
            .action-btn { padding: 5px 10px; margin: 0 2px; border: none; border-radius: 3px; cursor: pointer; font-size: 0.9em; }
            .action-start { background: #4CAF50; color: white; }
            .action-stop { background: #f44336; color: white; }
            footer { text-align: center; margin-top: 30px; color: #666; }
            .warning-box { background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🤖 Simple Bot Runner</h1>
                <p>Runs only <code>app.py</code> files • No Auto-Restart</p>
            </header>
            
            <div class="dashboard">
                <div class="warning-box">
                    ⚠️ <strong>NO AUTO-RESTART:</strong> If a bot crashes, it will stay stopped until manually restarted.
                </div>
                
                <div class="stats" id="stats">
                    <!-- Stats will be loaded here -->
                </div>
                
                <div class="controls">
                    <button class="btn btn-start" onclick="startAll()">▶ Start All</button>
                    <button class="btn btn-stop" onclick="stopAll()">⏹ Stop All</button>
                    <button class="btn btn-rescan" onclick="rescan()">🔍 Rescan</button>
                </div>
                
                <table class="bots-table" id="bots-table">
                    <thead>
                        <tr>
                            <th>Bot</th>
                            <th>Type</th>
                            <th>Status</th>
                            <th>PID</th>
                            <th>Uptime</th>
                            <th>Size</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="bots-body">
                        <!-- Bots will be loaded here -->
                    </tbody>
                </table>
            </div>
            
            <footer>
                <p>📁 Structure: <code>bots/bot1/app.py</code>, <code>bots/bot2/app.py</code>, etc.</p>
                <p>Only <code>app.py</code> files are run • No auto-restart on crash</p>
            </footer>
        </div>
        
        <script>
            async function loadDashboard() {
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    
                    // Update stats
                    document.getElementById('stats').innerHTML = `
                        <div class="stat-card">
                            <div class="stat-number">${data.total}</div>
                            <div>Total Bots</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number" style="color: #4CAF50">${data.running}</div>
                            <div>Running</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number" style="color: #f44336">${data.stopped}</div>
                            <div>Stopped</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.telegram_count}</div>
                            <div>Telegram</div>
                        </div>
                    `;
                    
                    // Update bots table
                    const tbody = document.getElementById('bots-body');
                    tbody.innerHTML = '';
                    
                    data.bots.forEach(bot => {
                        const row = document.createElement('tr');
                        
                        row.innerHTML = `
                            <td>
                                <strong>${bot.display_name}</strong><br>
                                <small>${bot.lines} lines • ${bot.has_requirements ? '📦' : '📄'}</small>
                            </td>
                            <td><span class="type-badge type-${bot.type}">${bot.type.toUpperCase()}</span></td>
                            <td><span class="status-badge status-${bot.running ? 'running' : 'stopped'}">${bot.running ? 'RUNNING' : 'STOPPED'}</span></td>
                            <td>${bot.running ? bot.pid : '-'}</td>
                            <td>${bot.uptime || '-'}</td>
                            <td>${(bot.file_size / 1024).toFixed(1)} KB</td>
                            <td>
                                ${bot.running ? 
                                    `<button class="action-btn action-stop" onclick="stopBot('${bot.id}')">Stop</button>` : 
                                    `<button class="action-btn action-start" onclick="startBot('${bot.id}')">Start</button>`
                                }
                            </td>
                        `;
                        
                        tbody.appendChild(row);
                    });
                    
                } catch (error) {
                    console.error('Error:', error);
                }
            }
            
            async function startBot(botId) {
                await fetch(`/api/start/${encodeURIComponent(botId)}`, { method: 'POST' });
                setTimeout(loadDashboard, 1000);
            }
            
            async function stopBot(botId) {
                await fetch(`/api/stop/${encodeURIComponent(botId)}`, { method: 'POST' });
                setTimeout(loadDashboard, 1000);
            }
            
            async function startAll() {
                await fetch('/api/start-all', { method: 'POST' });
                setTimeout(loadDashboard, 2000);
            }
            
            async function stopAll() {
                await fetch('/api/stop-all', { method: 'POST' });
                setTimeout(loadDashboard, 2000);
            }
            
            async function rescan() {
                await fetch('/api/rescan', { method: 'POST' });
                setTimeout(loadDashboard, 1000);
            }
            
            // Initial load
            loadDashboard();
            // Auto-refresh every 3 seconds
            setInterval(loadDashboard, 3000);
        </script>
    </body>
    </html>
    '''
    
    return html

@app.route('/api/status')
def api_status():
    status = runner.get_status()
    
    running = sum(1 for bot in status if bot["running"])
    stopped = len(status) - running
    telegram_count = sum(1 for bot in status if bot["type"] == "telegram")
    
    return jsonify({
        "success": True,
        "bots": status,
        "total": len(status),
        "running": running,
        "stopped": stopped,
        "telegram_count": telegram_count,
        "auto_restart": False
    })

@app.route('/api/start/<bot_id>', methods=['POST'])
def api_start_bot(bot_id):
    for bot in runner.bots:
        if bot["id"] == bot_id:
            success = runner.start_bot(bot)
            return jsonify({"success": success, "message": f"Started {bot['name']}"})
    return jsonify({"success": False, "message": "Bot not found"}), 404

@app.route('/api/stop/<bot_id>', methods=['POST'])
def api_stop_bot(bot_id):
    success = runner.stop_bot(bot_id)
    return jsonify({"success": success, "message": f"Stopped bot" if success else "Bot not running"})

@app.route('/api/start-all', methods=['POST'])
def api_start_all():
    runner.start_all_bots()
    return jsonify({"success": True, "message": "Starting all bots"})

@app.route('/api/stop-all', methods=['POST'])
def api_stop_all():
    runner.stop_all_bots()
    return jsonify({"success": True, "message": "Stopped all bots"})

@app.route('/api/rescan', methods=['POST'])
def api_rescan():
    runner.bots = []
    runner.scan_bots()
    return jsonify({"success": True, "message": "Rescanned bots", "count": len(runner.bots)})

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "bots": len(runner.bots),
        "running": len(runner.processes),
        "auto_restart": False
    })

def main():
    """Main function"""
    port = int(os.environ.get("PORT", 10000))
    
    logger.info("="*60)
    logger.info("🤖 SIMPLE BOT RUNNER (NO AUTO-RESTART)")
    logger.info("="*60)
    logger.info(f"Bots Directory: {BOTS_DIR}")
    logger.info("📌 Rule: Only runs app.py files")
    logger.info("⚠️  Important: NO AUTO-RESTART on crash")
    
    logger.info("\n📁 Structure:")
    logger.info(f"  {BOTS_DIR}/")
    logger.info("    bot1/app.py")
    logger.info("    bot2/app.py")
    logger.info("    bot3/app.py")
    
    if runner.bots:
        logger.info(f"\n✅ Found {len(runner.bots)} app.py file(s)")
    
    # Start web server
    logger.info(f"\n🌐 Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == "__main__":
    main()
