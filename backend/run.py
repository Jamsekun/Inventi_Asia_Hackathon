#!/usr/bin/env python3
"""
Property Management API Startup Script

This script provides an easy way to start the Property Management API server
with proper configuration and error handling.
"""

import os
import sys
import logging
import uvicorn
from dotenv import load_dotenv

# Add the backend directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function to start the API server"""
    
    # Get configuration from environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    # Validate configuration
    if not (1 <= port <= 65535):
        logger.error(f"Invalid port number: {port}. Must be between 1 and 65535.")
        sys.exit(1)
    
    if log_level not in ["debug", "info", "warning", "error", "critical"]:
        logger.warning(f"Invalid log level: {log_level}. Using 'info' instead.")
        log_level = "info"
    
    # Display startup information
    logger.info("=" * 60)
    logger.info("Property Management API Server")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Reload: {reload}")
    logger.info(f"Log Level: {log_level}")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info("=" * 60)
    
    # Check MongoDB connection
    mongodb_uri = os.getenv("MONGODB_URI")
    mongodb_db = os.getenv("MONGODB_DB", "MockPropDB")
    logger.info(f"MongoDB URI: {mongodb_uri}")
    logger.info(f"MongoDB Database: {mongodb_db}")
    
    try:
        # Start the server
        logger.info("Starting server...")
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
