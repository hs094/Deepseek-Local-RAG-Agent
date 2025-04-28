#!/usr/bin/env python3
"""
Helper script to start Qdrant locally without Docker.
This script checks if Qdrant is installed and running, and provides guidance if it's not.
"""

import os
import sys
import subprocess
import time
import webbrowser
import platform

def check_qdrant_installed():
    """Check if Qdrant is installed."""
    try:
        # Try to import qdrant_client
        import qdrant_client
        return True
    except ImportError:
        return False

def check_qdrant_running():
    """Check if Qdrant is running on localhost:6333."""
    import requests
    try:
        response = requests.get("http://localhost:6333/readiness", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_qdrant_docker():
    """Start Qdrant using Docker."""
    try:
        # Check if Docker is installed
        subprocess.run(["docker", "--version"], check=True, capture_output=True)
        
        # Check if Qdrant container exists
        result = subprocess.run(["docker", "ps", "-a", "--filter", "name=qdrant"], capture_output=True, text=True)
        
        if "qdrant" in result.stdout:
            # Container exists, check if it's running
            result = subprocess.run(["docker", "ps", "--filter", "name=qdrant"], capture_output=True, text=True)
            if "qdrant" in result.stdout:
                print("✅ Qdrant is already running in Docker")
                return True
            else:
                # Start the existing container
                print("🔄 Starting existing Qdrant container...")
                subprocess.run(["docker", "start", "qdrant"], check=True)
                time.sleep(2)  # Wait for container to start
                return True
        else:
            # Create and start a new container
            print("🔄 Creating and starting Qdrant container...")
            subprocess.run([
                "docker", "run", "-d", "--name", "qdrant",
                "-p", "6333:6333",
                "-p", "6334:6334",
                "-v", "qdrant_storage:/qdrant/storage",
                "qdrant/qdrant"
            ], check=True)
            time.sleep(3)  # Wait for container to start
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running Docker command: {e}")
        return False
    except FileNotFoundError:
        print("❌ Docker not found. Please install Docker or use pip to install Qdrant.")
        return False

def start_qdrant_pip():
    """Start Qdrant using pip installation."""
    try:
        # Check if qdrant server is installed
        subprocess.run(["qdrant", "--version"], check=True, capture_output=True)
        
        # Start qdrant server
        print("🔄 Starting Qdrant server...")
        
        # Create data directory if it doesn't exist
        os.makedirs("qdrant_data", exist_ok=True)
        
        # Start the server in the background
        if platform.system() == "Windows":
            subprocess.Popen(["start", "qdrant", "--db-path", "qdrant_data"], shell=True)
        else:
            subprocess.Popen(["qdrant", "--db-path", "qdrant_data"], 
                            stdout=subprocess.DEVNULL, 
                            stderr=subprocess.DEVNULL,
                            start_new_session=True)
        
        # Wait for server to start
        print("⏳ Waiting for Qdrant to start...")
        for _ in range(10):
            if check_qdrant_running():
                print("✅ Qdrant server started successfully")
                return True
            time.sleep(1)
        
        print("⚠️ Qdrant server might not have started properly. Check manually.")
        return False
        
    except subprocess.CalledProcessError:
        print("❌ Qdrant server not found. Please install it with: pip install qdrant-server")
        return False
    except FileNotFoundError:
        print("❌ Qdrant server not found. Please install it with: pip install qdrant-server")
        return False

def main():
    """Main function to start Qdrant."""
    print("🔍 Checking if Qdrant is already running...")
    
    # First check if Qdrant is already running
    try:
        import requests
        if check_qdrant_running():
            print("✅ Qdrant is already running on localhost:6333")
            print("🌐 Dashboard available at: http://localhost:6333/dashboard")
            
            # Open dashboard in browser
            if "--open-dashboard" in sys.argv:
                webbrowser.open("http://localhost:6333/dashboard")
                
            return True
    except ImportError:
        print("⚠️ requests package not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
        
        # Try again after installing requests
        import requests
        if check_qdrant_running():
            print("✅ Qdrant is already running on localhost:6333")
            return True
    
    # If not running, try to start it
    print("🔄 Qdrant is not running. Attempting to start...")
    
    # Try Docker first
    if start_qdrant_docker():
        print("🌐 Dashboard available at: http://localhost:6333/dashboard")
        
        # Open dashboard in browser
        if "--open-dashboard" in sys.argv:
            webbrowser.open("http://localhost:6333/dashboard")
            
        return True
    
    # If Docker fails, try pip installation
    print("⚠️ Docker method failed. Trying pip installation...")
    if start_qdrant_pip():
        print("🌐 Dashboard available at: http://localhost:6333/dashboard")
        
        # Open dashboard in browser
        if "--open-dashboard" in sys.argv:
            webbrowser.open("http://localhost:6333/dashboard")
            
        return True
    
    # If all methods fail, provide instructions
    print("\n❌ Failed to start Qdrant automatically.")
    print("\nPlease try one of the following methods:")
    print("\n1. Using Docker (recommended):")
    print("   docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant")
    
    print("\n2. Using pip:")
    print("   pip install qdrant-server")
    print("   qdrant --db-path qdrant_data")
    
    print("\n3. Manual installation:")
    print("   Follow the instructions at: https://qdrant.tech/documentation/guides/installation/")
    
    return False

if __name__ == "__main__":
    main()
