#!/usr/bin/env python3
"""
Wrapper script to handle psutil permission errors in Termux
"""
import os
import sys
import traceback

# Add bot path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress psutil permission errors
try:
    import psutil
    # Monkey patch to handle permission errors
    original_net_connections = psutil.net_connections
    def patched_net_connections(kind='inet'):
        try:
            return original_net_connections(kind)
        except (PermissionError, FileNotFoundError):
            return []
    
    psutil.net_connections = patched_net_connections
    
except ImportError:
    pass  # psutil not installed, that's okay

# Run the actual bot
try:
    print("🤖 Bot starting with wrapper...")
    import app
    # If app has a main function
    if hasattr(app, 'main'):
        app.main()
    elif __name__ == "__main__":
        # Import and run
        exec(open('app.py').read())
except Exception as e:
    print(f"❌ Bot error: {e}")
    traceback.print_exc()
    sys.exit(1)
