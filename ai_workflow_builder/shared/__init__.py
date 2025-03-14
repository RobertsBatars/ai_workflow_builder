# ai_workflow_builder/shared/__init__.py
"""
Shared components and models for the AI Workflow Builder application.
"""
import os
import logging
import logging.handlers
from pathlib import Path

def setup_logging(log_level=logging.INFO, log_to_file=True):
    """
    Set up logging for the application.
    
    Args:
        log_level: Logging level (default: INFO)
        log_to_file: Whether to log to file (default: True)
    
    Returns:
        Logger object
    """
    # Create logs directory if it doesn't exist
    if log_to_file:
        log_dir = Path.home() / ".ai_workflow_builder" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
    
    # Create logger
    logger = logging.getLogger("ai_workflow_builder")
    logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if log_to_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Create and export default logger
logger = setup_logging()