#!/usr/bin/env python3
"""
Telegram Bot Wrapper
Handles restart on crash and proper logging
"""
import os
import sys
import time
import logging
import traceback
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_runtime.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_bot():
    """Run the actual bot"""
    try:
        # Import and run bot
        sys.path.insert(0, os.path.dirname(__file__))
        
        logger.info("🤖 Loading bot module...")
        
        # Try different import methods
        try:
            # Method 1: Import as module
            import importlib.util
            spec = importlib.util.spec_from_file_location("bot_module", "app.py")
            bot_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(bot_module)
            logger.info("✅ Bot imported as module")
            
        except:
            # Method 2: Direct execution
            logger.info("🔄 Executing bot directly...")
            with open('app.py', 'r', encoding='utf-8') as f:
                exec(f.read(), {})
            logger.info("✅ Bot executed")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main loop - keeps bot running"""
    logger.info("="*60)
    logger.info("🚀 TELEGRAM BOT WRAPPER STARTED")
    logger.info("="*60)
    
    restart_count = 0
    max_restarts = 100
    
    while restart_count < max_restarts:
        try:
            restart_count += 1
            logger.info(f"🔄 Attempt {restart_count}/{max_restarts}")
            
            # Run the bot
            success = run_bot()
            
            if not success:
                logger.warning(f"Bot crashed, restarting in 10 seconds...")
                time.sleep(10)
            else:
                # If bot returns without error, it might have exited intentionally
                logger.info("Bot exited normally, restarting...")
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("👋 Received shutdown signal")
            break
        except Exception as e:
            logger.error(f"Wrapper error: {e}")
            logger.error(traceback.format_exc())
            time.sleep(30)
    
    logger.info("📛 Max restart attempts reached, stopping...")

if __name__ == "__main__":
    main()
