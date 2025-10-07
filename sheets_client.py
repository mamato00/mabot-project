"""
Google Sheets client for the finance chatbot.
"""

import logging
from datetime import datetime
import pandas as pd
import gspread
from typing import Dict, Optional, List, Any, Tuple
from google.oauth2.service_account import Credentials

logger = logging.getLogger("finance_chatbot")

class SheetsClient:
    def __init__(self, service_account_json: str, spreadsheet_id: str, sheet_name: str = "transactions"):
        self.service_account_json = service_account_json
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.gc = None
        self.sh = None
        self._connect()

    def _connect(self):
        try:
            logger.debug("Connecting to Google Sheets...")
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(self.service_account_json, scopes=scopes)
            self.gc = gspread.authorize(creds)
            self.sh = self.gc.open_by_key(self.spreadsheet_id)
            # ensure sheet exists
            try:
                self.sheet = self.sh.worksheet(self.sheet_name)
            except gspread.WorksheetNotFound:
                self.sheet = self.sh.add_worksheet(title=self.sheet_name, rows="1000", cols="20")
                # add header
                self.sheet.append_row(["timestamp", "date", "amount", "type", "category", "note"])
            logger.info("Connected to Google Sheets")
        except Exception as e:
            logger.exception("Failed to connect to Google Sheets")
            raise

    def append_transaction(self, txn: Dict[str, Any]) -> None:
        """
        txn keys: date, amount, type, category, note
        """
        try:
            row = [
                datetime.utcnow().isoformat(),
                txn.get("date"),
                float(txn.get("amount")),
                txn.get("type"),
                txn.get("category"),
                txn.get("note")
            ]
            logger.debug(f"Appending row to sheet: {row}")
            self.sheet.append_row(row, value_input_option="USER_ENTERED")
            logger.info("Transaction appended to Google Sheets")
        except Exception as e:
            logger.exception("Failed to append transaction to Google Sheets")
            raise

    def get_transactions_df(self) -> pd.DataFrame:
        try:
            records = self.sheet.get_all_records()
            df = pd.DataFrame(records)
            if df.empty:
                return df
            # ensure types
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
            df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date
            return df
        except Exception as e:
            logger.exception("Failed to read transactions from Google Sheets")
            raise
    
    def update_transaction(self, row_index: int, txn: Dict[str, Any]) -> None:
        """
        Update a transaction at the given row index (1-based index)
        """
        try:
            # Skip the header row, so row_index should be >= 2
            if row_index < 2:
                raise ValueError("Row index must be >= 2 (to skip header)")
            
            row = [
                datetime.utcnow().isoformat(),
                txn.get("date"),
                float(txn.get("amount")),
                txn.get("type"),
                txn.get("category"),
                txn.get("note")
            ]
            logger.debug(f"Updating row {row_index} in sheet: {row}")
            self.sheet.update(f"A{row_index}:F{row_index}", [row], value_input_option="USER_ENTERED")
            logger.info(f"Transaction at row {row_index} updated in Google Sheets")
        except Exception as e:
            logger.exception("Failed to update transaction in Google Sheets")
            raise
    
    def delete_transaction(self, row_index: int) -> None:
        """
        Delete a transaction at the given row index (1-based index)
        """
        try:
            # Skip the header row, so row_index should be >= 2
            if row_index < 2:
                raise ValueError("Row index must be >= 2 (to skip header)")
            
            logger.debug(f"Deleting row {row_index} from sheet")
            self.sheet.delete_rows(row_index)
            logger.info(f"Transaction at row {row_index} deleted in Google Sheets")
        except Exception as e:
            logger.exception("Failed to delete transaction in Google Sheets")
            raise