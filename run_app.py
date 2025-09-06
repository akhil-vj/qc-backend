#!/usr/bin/env python3
"""
QuickCart Backend Runner
========================

Easy-to-use script to run the QuickCart backend in different modes.

Usage:
    python run_app.py                    # Run simple server (default)
    python run_app.py --mode simple      # Run simple_server.py
    python run_app.py --mode main        # Run main FastAPI app
    python run_app.py --mode dev         # Development mode with auto-reload
    python run_app.py --mode prod        # Production mode
    python run_app.py --port 8001        # Custom port
    python run_app.py --host 127.0.0.1   # Custom host
"""

import argparse
import os
import sys
import subprocess
import time
from pathlib import Path

def print_banner():
    """Print application banner"""
    banner = """
╔═══════════════════════════════════════════════════════╗
║                 🚀 QuickCart Backend                  ║
║              Easy Backend Runner Script               ║
╚═══════════════════════════════════════════════════════╝
    """
    print(banner)

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import fastapi
        import uvicorn
        print("✅ FastAPI and Uvicorn are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("💡 Installing dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            return False

def check_environment():
    """Check if environment is properly set up"""
    print("\n🔍 Checking environment...")
    
    # Check if we're in the backend directory
    if not os.path.exists("simple_server.py"):
        print("❌ Not in backend directory. Please run from backend folder.")
        return False
    
    # Check for .env file
    if os.path.exists(".env"):
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found, using defaults")
    
    # Check database
    if os.path.exists("quickcart.db"):
        print("✅ Database file found")
    else:
        print("⚠️  Database file not found (will be created)")
    
    return True

def run_simple_server(host="0.0.0.0", port=8000):
    """Run the simple server"""
    print(f"\n🚀 Starting Simple Server on {host}:{port}")
    print("📋 Features: Basic API endpoints, CORS enabled")
    print("🔗 Access at: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/docs")
    print("\n" + "="*50)
    
    try:
        import uvicorn
        uvicorn.run(
            "simple_server:app",
            host=host,
            port=port,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

def run_main_app(host="0.0.0.0", port=8000, reload=True):
    """Run the main FastAPI application"""
    print(f"\n🚀 Starting Main Application on {host}:{port}")
    print("📋 Features: Full app with middleware, database, authentication")
    print("🔗 Access at: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/docs")
    print("\n" + "="*50)
    
    try:
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

def run_with_docker():
    """Run using Docker"""
    print("\n🐳 Starting with Docker...")
    try:
        subprocess.run(["docker-compose", "up", "--build"], check=True)
    except subprocess.CalledProcessError:
        print("❌ Docker failed. Make sure Docker is installed and running.")
    except FileNotFoundError:
        print("❌ Docker not found. Please install Docker.")

def main():
    parser = argparse.ArgumentParser(
        description="QuickCart Backend Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_app.py                      # Simple server on port 8000
  python run_app.py --mode main          # Full app with all features
  python run_app.py --port 8001          # Custom port
  python run_app.py --mode dev           # Development mode
  python run_app.py --mode prod          # Production mode
  python run_app.py --docker             # Run with Docker
        """
    )
    
    parser.add_argument(
        "--mode", 
        choices=["simple", "main", "dev", "prod"], 
        default="main",
        help="Server mode (default: main)"
    )
    parser.add_argument(
        "--host", 
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--docker", 
        action="store_true",
        help="Run using Docker"
    )
    parser.add_argument(
        "--no-reload", 
        action="store_true",
        help="Disable auto-reload"
    )
    parser.add_argument(
        "--install-deps", 
        action="store_true",
        help="Install dependencies before running"
    )
    
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Install dependencies if requested
    if args.install_deps:
        if not check_dependencies():
            return 1
    
    # Check environment
    if not check_environment():
        return 1
    
    # Run with Docker
    if args.docker:
        run_with_docker()
        return 0
    
    # Determine reload setting
    reload = not args.no_reload and args.mode != "prod"
    
    # Run based on mode
    if args.mode == "simple":
        run_simple_server(args.host, args.port)
    elif args.mode in ["main", "dev", "prod"]:
        run_main_app(args.host, args.port, reload)
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
