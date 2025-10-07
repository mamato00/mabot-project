"""
Configuration and initialization for the finance chatbot.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv() 

# Read config from env for easier deployment
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON", "service_account.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", None)  # required
SHEET_NAME = os.getenv("SHEET_NAME", "transactions")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)  # required

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