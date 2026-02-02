# services/data_logger.py

import logging
from logging.handlers import RotatingFileHandler
import os
import sys

# This allows importing the config file from the project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config

def setup_logging():
    """
    Configures the root logger for the Krishinetra application.

    This function sets up a sophisticated logging system that outputs logs
    to both the console and two separate, rotating log files: one for general
    information and another exclusively for errors and warnings.
    """
    log_dir = os.path.dirname(config.LOG_FILE_PATH)
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    log_format = logging.Formatter(
        '%(asctime)s - %(name)-22s - [%(levelname)-8s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # --- 1. Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # --- 2. Main Rotating File Handler ---
    info_file_handler = RotatingFileHandler(
        config.LOG_FILE_PATH,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding='utf-8'
    )
    info_file_handler.setLevel(logging.INFO)
    info_file_handler.setFormatter(log_format)
    root_logger.addHandler(info_file_handler)

    # --- 3. Error Rotating File Handler ---
    error_file_handler = RotatingFileHandler(
        config.ERROR_LOG_FILE_PATH,
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=3,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.WARNING)
    error_file_handler.setFormatter(log_format)
    root_logger.addHandler(error_file_handler)

    root_logger.info("--------------------------------------------------")
    root_logger.info(f"Logging for '{config.PROJECT_NAME}' initialized.")
    root_logger.info(f"Console & Info Log Level set to: {config.LOG_LEVEL}")
    root_logger.info(f"General Log File: {config.LOG_FILE_PATH}")
    root_logger.info(f"Error Log File:   {config.ERROR_LOG_FILE_PATH}")
    root_logger.info("--------------------------------------------------")