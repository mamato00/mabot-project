"""
Configuration and initialization for the finance chatbot.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv() 

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", None)  # Neon database URL
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")  # For session management

# Google Sheets configuration
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON", "service_account.json")
SHEET_NAME = os.getenv("SHEET_NAME", "transactions")

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)  # required

# Template spreadsheet URL
TEMPLATE_SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1abc123def456ghi789jkl012mno345pqr678stu901vwxyz/edit#gid=0"

# --- Logging setup ---
LOG_FILENAME = "finance_chatbot.log"
logger = logging.getLogger("finance_chatbot")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)

# Also add Stream handler for console (helpful in debugging)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)