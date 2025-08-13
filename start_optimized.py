#!/usr/bin/env python3
"""
High-performance startup script for Mala Booking System
Optimized for production workloads with reduced latency
"""

import uvicorn
import multiprocessing
import os
import sys
from pathlib import Path

def get_optimal_workers():
    """Calculate optimal number of workers based on CPU cores"""
    cpu_count = multiprocessing.cpu_count()
    # For I/O bound applications like FastAPI with database operations
    # Use 2x CPU cores, but cap at 8 for memory efficiency
    optimal_workers = min(max(2, cpu_count * 2), 8)
    return optimal_workers

def main():
    """Start the application with optimized settings"""
    
    # Set environment variables for better performance
    os.environ.setdefault("PYTHONPATH", str(Path(__file__).parent))
    os.environ.setdefault("WORKERS", str(get_optimal_workers()))
    
    # Performance optimizations
    config = {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": int(os.environ.get("PORT", 8000)),
        "workers": int(os.environ.get("WORKERS", get_optimal_workers())),
        "worker_class": "uvicorn.workers.UvicornWorker",
        "loop": "uvloop",  # Use uvloop for better performance
        "http": "httptools",  # Use httptools for faster HTTP parsing
        "log_level": os.environ.get("LOG_LEVEL", "info"),
        "access_log": True,
        "use_colors": True,
        "reload": False,  # Disable in production
        "preload_app": True,  # Preload for better memory efficiency
        
        # Connection settings
        "backlog": 2048,  # Increased backlog for high load
        "max_requests": 1000,  # Restart workers after N requests
        "max_requests_jitter": 50,  # Add randomness to prevent thundering herd
        "timeout": 30,  # Worker timeout
        "keepalive": 5,  # Keep connections alive for better performance
        
        # SSL settings (uncomment for production with HTTPS)
        # "ssl_keyfile": os.environ.get("SSL_KEYFILE"),
        # "ssl_certfile": os.environ.get("SSL_CERTFILE"),
    }
    
    # Remove None values
    config = {k: v for k, v in config.items() if v is not None}
    
    print("🚀 Starting Mala Booking System with optimized settings...")
    print(f"📊 Workers: {config['workers']}")
    print(f"🌐 Host: {config['host']}:{config['port']}")
    print(f"⚡ Loop: {config['loop']}")
    print(f"🔗 HTTP Parser: {config['http']}")
    
    # Start with Gunicorn for production or Uvicorn for development
    if config["workers"] > 1 and not os.environ.get("DEVELOPMENT"):
        try:
            import gunicorn.app.wsgiapp as wsgi
            # Use Gunicorn for multi-worker setup
            sys.argv = [
                "gunicorn",
                f"--bind={config['host']}:{config['port']}",
                f"--workers={config['workers']}",
                f"--worker-class=uvicorn.workers.UvicornWorker",
                f"--worker-connections=1000",
                f"--max-requests={config['max_requests']}",
                f"--max-requests-jitter={config['max_requests_jitter']}",
                f"--timeout={config['timeout']}",
                f"--keepalive={config['keepalive']}",
                f"--backlog={config['backlog']}",
                "--preload",
                "--log-level=info",
                config["app"]
            ]
            from gunicorn.app.wsgiapp import run
            run()
        except ImportError:
            print("⚠️  Gunicorn not available, falling back to Uvicorn")
            uvicorn.run(**config)
    else:
        # Single worker mode (development)
        config["workers"] = 1
        uvicorn.run(**config)

if __name__ == "__main__":
    main()