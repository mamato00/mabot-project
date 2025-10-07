"""
Utility functions for the finance chatbot.
"""

import re
import logging
from datetime import datetime, date, timedelta
from dateutil import parser as dateparser
from typing import Dict, Optional, List, Any, Tuple
import pandas as pd
import json

logger = logging.getLogger("finance_chatbot")

class ParseError(Exception):
    pass

def parse_credentials_string(credentials_string: str) -> Dict[str, Any]:
    """
    Parse credentials from a JSON string.
    
    Args:
        credentials_string: JSON string containing the credentials
    
    Returns:
        Dictionary containing the credentials
    """
    try:
        credentials = json.loads(credentials_string)
        logger.info("Successfully parsed credentials from environment variable")
        return credentials
    except json.JSONDecodeError as e:
        logger.exception(f"Failed to parse credentials string: {e}")
        raise ValueError("Invalid JSON format for GOOGLE_SHEETS_JSON. Please check your .env file.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred while parsing credentials: {e}")
        raise

def parse_amount(text: str) -> float:
    """
    Parse amount like '50k', 'Rp 1.200.000', '1,200.50', '1000' -> float (IDR decimal)
    """
    original = text
    try:
        text = text.lower().strip()
        # remove currency symbols
        text = re.sub(r"[^\d,.\-k]", "", text)
        # handle 'k' shorthand
        if "k" in text:
            num = re.sub(r"[k]", "", text)
            num = num.replace(",", ".")
            value = float(num) * 1000
            logger.debug(f"parse_amount: '{original}' -> {value}")
            return value
        # replace thousands separators if dots used
        # detect pattern like 1.200.000 or 1,200,000
        if text.count(".") > 1 and "," not in text:
            text = text.replace(".", "")
        elif text.count(",") > 1 and "." not in text:
            text = text.replace(",", "")
        # unify comma as decimal if needed
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        value = float(text)
        logger.debug(f"parse_amount: '{original}' -> {value}")
        return value
    except Exception as e:
        logger.exception("Failed parsing amount")
        raise ParseError(f"cannot parse amount from '{original}': {e}")

def normalize_category(cat: Optional[str]) -> str:
    if not cat:
        return "uncategorized"
    cat = cat.strip().lower()
    mapping = {
        "makan": "food",
        "makanan": "food",
        "transport": "transport",
        "transportasi": "transport",
        "gaji": "income",
        "bayar": "bills",
        "tagihan": "bills",
        "belanja": "shopping",
        "hiburan": "entertainment",
        "kesehatan": "health",
        "pendidikan": "education",
    }
    return mapping.get(cat, cat.replace(" ", "_"))

def format_amount(amount: float) -> str:
    """
    Format amount to Indonesian format: 1.200.000,50 (dot as thousand separator, comma as decimal)
    """
    try:
        # Format to 2 decimal places
        formatted = f"{amount:,.2f}"
        # Replace comma with dot for thousand separator
        formatted = formatted.replace(",", "X")
        # Replace dot with comma for decimal separator
        formatted = formatted.replace(".", ",")
        # Replace X with dot for thousand separator
        formatted = formatted.replace("X", ".")
        return formatted
    except Exception as e:
        logger.exception("Failed formatting amount")
        return str(amount)

def paginate_dataframe(df, page_size, page_num):
    """Return a subset of the dataframe for the given page number."""
    start_idx = (page_num - 1) * page_size
    end_idx = start_idx + page_size
    return df.iloc[start_idx:end_idx]

def extract_spreadsheet_id_from_url(url: str) -> Optional[str]:
    """
    Extract spreadsheet ID from Google Sheets URL.
    """
    try:
        # Pattern for Google Sheets URL
        pattern = r"/spreadsheets/d/([a-zA-Z0-9-_]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        logger.exception(f"Failed to extract spreadsheet ID from URL: {url}")
        return None