#!/usr/bin/env python3
"""
Run the Gmail ETL FastAPI server with MCP and OpenTelemetry
"""

import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.api.server import app
from src.api.telemetry import setup_telemetry
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Run the API server"""
    logger.info("Starting Gmail ETL API server...")
    
    # OpenTelemetry is set up automatically on import
    
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()