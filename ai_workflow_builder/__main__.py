#!/usr/bin/env python3
"""
Main entry point for the AI Workflow Builder application.
"""
import sys
import os
import argparse
import multiprocessing
import threading
import time
import subprocess
import uvicorn
from typing import Optional

# Ensure multiprocessing works correctly 
if sys.platform == 'win32':
    multiprocessing.freeze_support()

# Add parent directory to path for development mode
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import application components
try:
    # Try importing main dependencies
    from PySide6.QtWidgets import QApplication
    
    # Try to install missing packages automatically if needed
    missing_packages = []
    
    try:
        import NodeGraphQt
    except ImportError:
        missing_packages.append("NodeGraphQt")
        
    try:
        import Qt
    except ImportError:
        missing_packages.append("Qt.py")
        
    # Check for other critical packages
    for package in ["tiktoken", "fastapi", "uvicorn", "faiss-cpu"]:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    # If missing packages, try to install them
    if missing_packages:
        print(f"Attempting to install missing packages: {', '.join(missing_packages)}")
        try:
            import pip
            for package in missing_packages:
                print(f"Installing {package}...")
                pip.main(["install", package])
            print("Installation complete. Continuing...")
        except Exception as install_error:
            print(f"Error installing packages: {install_error}")
            print("Please install required dependencies manually with:")
            print("    pip install -r requirements.txt")
    
    # Now import the app components
    from ai_workflow_builder.frontend.main_window import MainWindow
    from ai_workflow_builder.backend.api import app_asgi
    
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please install required dependencies with:")
    print("    pip install -r requirements.txt")
    print("\nIf you're on Windows, make sure to run:")
    print("    pip install -e .")
    sys.exit(1)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="AI Workflow Builder")
    
    parser.add_argument('--headless', action='store_true', 
                        help='Run in headless mode (API server only)')
    
    parser.add_argument('--host', type=str, default='localhost',
                        help='Host to bind the API server (default: localhost)')
    
    parser.add_argument('--port', type=int, default=8000,
                        help='Port to bind the API server (default: 8000)')
    
    parser.add_argument('--debug', action='store_true',
                        help='Run in debug mode')
    
    parser.add_argument('--version', action='store_true',
                        help='Show version information')
    
    return parser.parse_args()


def run_api_server(host: str = 'localhost', port: int = 8000, debug: bool = False):
    """Run the API server using uvicorn."""
    uvicorn.run(app_asgi, host=host, port=port, log_level="debug" if debug else "info")


def run_frontend():
    """Run the frontend application."""
    app = QApplication(sys.argv)
    app.setApplicationName("AI Workflow Builder")
    app.setOrganizationName("AI Workflow Builder")
    app.setOrganizationDomain("ai-workflow-builder.local")
    
    # Create and show the main window
    main_window = MainWindow(app)
    main_window.show()
    
    # Run the application event loop
    sys.exit(app.exec())


def start_api_in_thread(host: str, port: int, debug: bool):
    """Start the API server in a separate thread."""
    api_thread = threading.Thread(
        target=run_api_server, 
        args=(host, port, debug),
        daemon=True
    )
    api_thread.start()
    
    # Wait for the API server to start
    time.sleep(1)
    
    return api_thread


def main():
    """Main entry point."""
    args = parse_args()
    
    if args.version:
        from ai_workflow_builder import __version__
        print(f"AI Workflow Builder v{__version__}")
        return 0
    
    if args.headless:
        # Run only the API server
        run_api_server(args.host, args.port, args.debug)
    else:
        # Run the API server in a thread and the frontend in the main thread
        api_thread = start_api_in_thread(args.host, args.port, args.debug)
        run_frontend()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())