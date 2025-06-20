# Gmail ETL FastAPI Server Package

from .server import app
from .telemetry import setup_telemetry

__all__ = ["app", "setup_telemetry"]