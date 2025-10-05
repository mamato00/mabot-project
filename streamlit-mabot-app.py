"""
streamlit_app.py
Chatbot AI Gemini pencatat keuangan pribadi (Streamlit) + Google Sheets integration.

Langkah cepat:
1) pip install -r requirements.txt
2) Siapkan Google Service Account JSON, beri akses edit pada spreadsheet, catat SPREADSHEET_ID
3) Set env vars: GOOGLE_SHEETS_JSON=/path/to/creds.json, SPREADSHEET_ID=<id>, GEMINI_API_KEY=<key>
4) streamlit run streamlit_app.py
"""

from dotenv import load_dotenv
import os
load_dotenv() 

import json
import logging
from datetime import datetime, date, timedelta
from dateutil import parser as dateparser
from typing import Dict, Optional, List, Any, Tuple
import re
import io

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Google Sheets
import gspread
from google.oauth2.service_account import Credentials

# LangChain & Gemini
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.output_parsers import JsonOutputToolsParser
from langchain.chains import LLMChain
from langchain.agents import AgentExecutor, create_react_agent, Tool
from langchain.memory import ConversationBufferMemory

# --- CONFIG ---
LOG_FILENAME = "finance_chatbot.log"
# Read config from env for easier deployment
GOOGLE_SHEETS_JSON = os.getenv("GOOGLE_SHEETS_JSON", "service_account.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", None)  # required
SHEET_NAME = os.getenv("SHEET_NAME", "transactions")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)  # required

# --- Logging setup ---
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


# ---------------------------
# Utility helpers & parser
# ---------------------------
class ParseError(Exception):
    pass


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

# ---------------------------
# Gemini Client with LangChain
# ---------------------------
class GeminiClient:
    """
    Gemini Flash 2.5 API client for transaction parsing using LangChain.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        # Initialize LangChain with Gemini 2.5 Flash
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",  # Using Gemini 2.5 Flash
            google_api_key=api_key,
            temperature=0.1,
            convert_system_message_to_human=True
        )
        logger.info("Gemini client initialized with LangChain")

    def generate(self, prompt: str, max_tokens: int = 512) -> str:
        """
        Generate text from prompt using Gemini Flash 2.5 via LangChain.
        """
        logger.info(f"GeminiClient.generate called")
        try:
            messages = [HumanMessage(content=prompt)]
            response = self.model.invoke(messages)
            return response.content
        except Exception as e:
            logger.exception("Gemini API error")
            raise Exception(f"Gemini API error: {e}")

    def is_transaction(self, text: str) -> Tuple[bool, str, str]:
        """
        Determine if the text is about a financial transaction, a data query, or just a conversation.
        Returns a tuple of (is_transaction, is_data_query, reasoning, response)
        """
        prompt = f"""
        Analyze the following text in Indonesian and determine what type of request it is:
        
        1. Is it about a financial transaction (adding a new expense/income)?
        2. Is it a query about existing financial data?
        3. Is it just a general conversation?
        
        Use chain of thought to analyze:
        1. Does the text mention adding, recording, or inputting money, spending, or income?
        2. Does it contain specific amounts or prices for a new transaction?
        3. Is it describing a purchase, payment, or earning that happened?
        4. Or is it asking questions about existing data (e.g., "what's my biggest expense?", "how much did I spend on food?")?
        
        Text: "{text}"
        
        Return a JSON object with these keys:
        - is_transaction: true if it's about adding a new financial transaction, false otherwise
        - is_data_query: true if it's asking about existing financial data, false otherwise
        - reasoning: brief explanation of your decision
        - response: a friendly response to the user (if it's just a conversation)
        
        Only return valid JSON, nothing else.
        """
        
        try:
            response = self.generate(prompt)
            logger.debug(f"Gemini is_transaction raw response: {response}")
            
            # Clean up response to ensure it's valid JSON
            json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to extract JSON directly
                json_str = response.strip()
            
            parsed = json.loads(json_str)
            return (
                parsed.get("is_transaction", False), 
                parsed.get("is_data_query", False), 
                parsed.get("reasoning", ""), 
                parsed.get("response", "")
            )
        except Exception as e:
            logger.exception("Failed to determine text type")
            # Default to treating as transaction if analysis fails
            return True, False, "Analysis failed, defaulting to transaction", ""

    def parse_transaction(self, text: str) -> Dict[str, Any]:
        """
        Parse transaction from natural language text using Gemini with chain of thought via LangChain.
        """
        today_str = date.today().isoformat()
        prompt = f"""
        Extract transaction information from the following text in Indonesian.
        
        Use chain of thought to analyze:
        1. Identify the date of the transaction (if not mentioned, use today's date which is {today_str})
        2. Identify the amount - if there are quantities and unit prices, calculate the total
        3. Determine if it's an expense or income
        4. Categorize the transaction appropriately
        5. Extract a brief description/note
        
        Text: "{text}"
        
        Return a JSON object with these keys:
        - date: transaction date in YYYY-MM-DD format
        - amount: numeric value without currency symbols
        - type: either "expense" or "income"
        - category: one of these categories: food, transport, shopping, bills, entertainment, health, education, income, or uncategorized
        - note: brief description of the transaction
        - reasoning: brief explanation of how you calculated the amount
        
        Only return valid JSON, nothing else.
        """
        
        try:
            response = self.generate(prompt)
            logger.debug(f"Gemini raw response: {response}")
            
            # Clean up response to ensure it's valid JSON
            json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to extract JSON directly
                json_str = response.strip()
            
            parsed = json.loads(json_str)
            
            # Normalize values
            if "amount" in parsed:
                parsed["amount"] = parse_amount(str(parsed["amount"]))
            if "category" in parsed:
                parsed["category"] = normalize_category(parsed.get("category"))
            
            return parsed
        except Exception as e:
            logger.exception("Failed to parse transaction with Gemini")
            raise ParseError(f"Failed to parse transaction: {e}")

    def generate_friendly_response(self, text: str) -> str:
        """
        Generate a friendly conversational response for non-transaction text.
        """
        prompt = f"""
        Generate a friendly, conversational response to the following text in Indonesian.
        The user is talking to a finance chatbot, but this message is not about a transaction or data query.
        
        Text: "{text}"
        
        Your response should:
        1. Be friendly and conversational
        2. Acknowledge what the user said
        3. Gently remind them that you're here to help with financial transactions and data analysis
        4. Keep it brief and natural
        5. Use Jaksel Indonesia style language such as gw, lo, mantap, etc.
        
        Only return the response text, nothing else.
        """
        
        try:
            response = self.generate(prompt)
            logger.debug(f"Gemini friendly response: {response}")
            return response.strip()
        except Exception as e:
            logger.exception("Failed to generate friendly response")
            return "Maaf, saya tidak dapat memproses pesan Anda. Saya di sini untuk membantu mencatat transaksi keuangan Anda dan menganalisis data Anda."

    def analyze_data_query(self, text: str, data_summary: str) -> str:
        """
        Analyze a data query using the provided data summary.
        """
        prompt = f"""
        Analyze the following user query about financial data and provide a helpful response based on the data summary.
        
        User query: "{text}"
        
        Data summary:
        {data_summary}
        
        Your response should:
        1. Directly answer the user's question based on the data
        2. Provide specific numbers and details when possible
        3. Be conversational and friendly
        4. Use Jaksel Indonesia style language such as gw, lo, mantap, etc.
        5. If the data doesn't contain enough information to answer the question, explain what data would be needed
        
        Only return the response text, nothing else.
        """
        
        try:
            response = self.generate(prompt, max_tokens=1024)
            logger.debug(f"Gemini data analysis response: {response}")
            return response.strip()
        except Exception as e:
            logger.exception("Failed to analyze data query")
            return "Maaf, saya tidak dapat menganalisis data Anda saat ini. Silakan coba lagi nanti."


# ---------------------------
# Data Analysis Tools
# ---------------------------
class DataAnalyzer:
    """
    Tools for analyzing financial data from Google Sheets.
    """
    
    def __init__(self, sheets_client):
        self.sheets_client = sheets_client
    
    def get_data_summary(self) -> str:
        """
        Generate a comprehensive summary of the financial data for AI analysis.
        """
        try:
            df = self.sheets_client.get_transactions_df()
            if df.empty:
                return "Tidak ada data transaksi yang tersedia."
            
            # Convert date to datetime for analysis
            df['date'] = pd.to_datetime(df['date'])
            
            # Basic statistics
            total_income = df[df['type'] == 'income']['amount'].sum()
            total_expense = df[df['type'] == 'expense']['amount'].sum()
            balance = total_income - total_expense
            
            # Monthly trends
            current_month = datetime.now().replace(day=1)
            last_month = (current_month - timedelta(days=1)).replace(day=1)
            
            current_month_data = df[df['date'] >= current_month]
            last_month_data = df[(df['date'] >= last_month) & (df['date'] < current_month)]
            
            current_month_income = current_month_data[current_month_data['type'] == 'income']['amount'].sum()
            current_month_expense = current_month_data[current_month_data['type'] == 'expense']['amount'].sum()
            
            last_month_income = last_month_data[last_month_data['type'] == 'income']['amount'].sum()
            last_month_expense = last_month_data[last_month_data['type'] == 'expense']['amount'].sum()
            
            # Category breakdown
            expense_by_category = df[df['type'] == 'expense'].groupby('category')['amount'].sum().sort_values(ascending=False)
            income_by_category = df[df['type'] == 'income'].groupby('category')['amount'].sum().sort_values(ascending=False)
            
            # Top expenses
            top_expenses = df[df['type'] == 'expense'].sort_values('amount', ascending=False).head(10)
            
            # Recent transactions
            recent_transactions = df.sort_values('date', ascending=False).head(10)
            
            # Build summary text
            summary = f"""
RINGKASAN DATA KEUANGAN:

STATISTIK UMUM:
- Total Pemasukan: Rp {total_income:,.2f}
- Total Pengeluaran: Rp {total_expense:,.2f}
- Saldo Bersih: Rp {balance:,.2f}
- Jumlah Transaksi: {len(df)}

TREN BULANAN:
Bulan Ini ({current_month.strftime('%B %Y')}):
- Pemasukan: Rp {current_month_income:,.2f}
- Pengeluaran: Rp {current_month_expense:,.2f}

Bulan Lalu ({last_month.strftime('%B %Y')}):
- Pemasukan: Rp {last_month_income:,.2f}
- Pengeluaran: Rp {last_month_expense:,.2f}

PENGELUARAN PER KATEGORI:
"""
            for category, amount in expense_by_category.items():
                summary += f"- {category}: Rp {amount:,.2f} ({amount/total_expense*100:.1f}%)\n"
            
            summary += "\nPEMASUKAN PER KATEGORI:\n"
            for category, amount in income_by_category.items():
                summary += f"- {category}: Rp {amount:,.2f} ({amount/total_income*100:.1f}%)\n"
            
            summary += "\n10 TRANSAKSI TERBESAR:\n"
            for _, row in top_expenses.iterrows():
                summary += f"- {row['date'].strftime('%d/%m/%Y')}: {row['note']} ({row['category']}) - Rp {row['amount']:,.2f}\n"
            
            summary += "\n10 TRANSAKSI TERAKHIR:\n"
            for _, row in recent_transactions.iterrows():
                summary += f"- {row['date'].strftime('%d/%m/%Y')}: {row['note']} ({row['category']}) - Rp {row['amount']:,.2f} ({row['type']})\n"
            
            return summary
        except Exception as e:
            logger.exception("Failed to generate data summary")
            return f"Error generating data summary: {str(e)}"
    
    def get_expenses_by_category(self, category: str = None, period: str = "all") -> str:
        """
        Get expenses by category, optionally filtered by category and period.
        Period can be "all", "current_month", "last_month", or "last_3_months"
        """
        try:
            df = self.sheets_client.get_transactions_df()
            if df.empty:
                return "Tidak ada data transaksi yang tersedia."
            
            # Convert date to datetime for analysis
            df['date'] = pd.to_datetime(df['date'])
            
            # Filter by period
            today = datetime.now().date()
            if period == "current_month":
                start_date = today.replace(day=1)
                df = df[df['date'] >= start_date]
            elif period == "last_month":
                current_month_start = today.replace(day=1)
                last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
                df = df[(df['date'] >= last_month_start) & (df['date'] < current_month_start)]
            elif period == "last_3_months":
                start_date = (today.replace(day=1) - timedelta(days=90))
                df = df[df['date'] >= start_date]
            
            # Filter by type (expense only)
            df = df[df['type'] == 'expense']
            
            # Filter by category if specified
            if category and category != "all":
                df = df[df['category'] == category]
            
            if df.empty:
                return f"Tidak ada data pengeluaran yang ditemukan untuk kategori '{category}' dalam periode {period}."
            
            # Group by category and sum
            category_expenses = df.groupby('category')['amount'].sum().sort_values(ascending=False)
            
            # Build result text
            result = f"PENGELUARAN"
            if category and category != "all":
                result += f" UNTUK KATEGORI '{category}'"
            result += f" ({period}):\n\n"
            
            for cat, amount in category_expenses.items():
                result += f"- {cat}: Rp {amount:,.2f}\n"
            
            result += f"\nTotal: Rp {category_expenses.sum():,.2f}"
            
            return result
        except Exception as e:
            logger.exception("Failed to get expenses by category")
            return f"Error getting expenses: {str(e)}"
    
    def get_income_by_category(self, category: str = None, period: str = "all") -> str:
        """
        Get income by category, optionally filtered by category and period.
        Period can be "all", "current_month", "last_month", or "last_3_months"
        """
        try:
            df = self.sheets_client.get_transactions_df()
            if df.empty:
                return "Tidak ada data transaksi yang tersedia."
            
            # Convert date to datetime for analysis
            df['date'] = pd.to_datetime(df['date'])
            
            # Filter by period
            today = datetime.now().date()
            if period == "current_month":
                start_date = today.replace(day=1)
                df = df[df['date'] >= start_date]
            elif period == "last_month":
                current_month_start = today.replace(day=1)
                last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
                df = df[(df['date'] >= last_month_start) & (df['date'] < current_month_start)]
            elif period == "last_3_months":
                start_date = (today.replace(day=1) - timedelta(days=90))
                df = df[df['date'] >= start_date]
            
            # Filter by type (income only)
            df = df[df['type'] == 'income']
            
            # Filter by category if specified
            if category and category != "all":
                df = df[df['category'] == category]
            
            if df.empty:
                return f"Tidak ada data pemasukan yang ditemukan untuk kategori '{category}' dalam periode {period}."
            
            # Group by category and sum
            category_income = df.groupby('category')['amount'].sum().sort_values(ascending=False)
            
            # Build result text
            result = f"PEMASUKAN"
            if category and category != "all":
                result += f" UNTUK KATEGORI '{category}'"
            result += f" ({period}):\n\n"
            
            for cat, amount in category_income.items():
                result += f"- {cat}: Rp {amount:,.2f}\n"
            
            result += f"\nTotal: Rp {category_income.sum():,.2f}"
            
            return result
        except Exception as e:
            logger.exception("Failed to get income by category")
            return f"Error getting income: {str(e)}"
    
    def get_transactions_by_keyword(self, keyword: str, limit: int = 10) -> str:
        """
        Get transactions containing a specific keyword in the note.
        """
        try:
            df = self.sheets_client.get_transactions_df()
            if df.empty:
                return "Tidak ada data transaksi yang tersedia."
            
            # Filter by keyword in note
            filtered_df = df[df['note'].str.contains(keyword, case=False, na=False)]
            
            if filtered_df.empty:
                return f"Tidak ada transaksi yang ditemukan dengan kata kunci '{keyword}'."
            
            # Sort by date (most recent first) and limit
            filtered_df = filtered_df.sort_values('date', ascending=False).head(limit)
            
            # Build result text
            result = f"TRANSAKSI DENGAN KATA KUNCI '{keyword}':\n\n"
            
            for _, row in filtered_df.iterrows():
                result += f"- {row['date'].strftime('%d/%m/%Y')}: {row['note']} ({row['category']}) - Rp {row['amount']:,.2f} ({row['type']})\n"
            
            return result
        except Exception as e:
            logger.exception("Failed to get transactions by keyword")
            return f"Error getting transactions: {str(e)}"


# ---------------------------
# Google Sheets Client
# ---------------------------
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


# ---------------------------
# Streamlit App
# ---------------------------
def initialize_state():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "debug_mode" not in st.session_state:
        st.session_state.debug_mode = False
    if "debug_logs" not in st.session_state:
        st.session_state.debug_logs = []
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False
    if "edit_row_index" not in st.session_state:
        st.session_state.edit_row_index = None
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

def add_debug(msg: str):
    if st.session_state.debug_mode:
        st.session_state.debug_logs.append(f"{datetime.now().isoformat()} - {msg}")
        logger.debug(msg)

def clear_chat():
    st.session_state.chat_history = []
    if "pending_transaction" in st.session_state:
        del st.session_state.pending_transaction
    st.session_state.memory.clear()

def process_user_input(user_input: str, gemini_client, data_analyzer):
    """
    Process user input and generate appropriate response.
    """
    if not user_input:
        return
    
    add_debug(f"User input: {user_input}")
    
    with st.spinner("Sedang memproses..."):
        try:
            # First, determine if this is a transaction, data query, or just conversation
            is_transaction, is_data_query, reasoning, friendly_response = gemini_client.is_transaction(user_input)
            add_debug(f"Is transaction: {is_transaction}, Is data query: {is_data_query}, Reasoning: {reasoning}")
            
            if is_data_query and data_analyzer:
                # It's a data query, analyze the data
                data_summary = data_analyzer.get_data_summary()
                response = gemini_client.analyze_data_query(user_input, data_summary)
                st.session_state.chat_history.append({
                    "role": "bot", 
                    "text": response
                })
            elif is_transaction:
                # It's a transaction, parse it
                parsed_txn = gemini_client.parse_transaction(user_input)
                add_debug(f"Parsed transaction: {parsed_txn}")
                
                # Create a friendly response with the parsed transaction
                reasoning = parsed_txn.get("reasoning", "")
                if reasoning:
                    reasoning_text = f"\n\nPerhitungan: {reasoning}"
                else:
                    reasoning_text = ""
                
                st.session_state.chat_history.append({
                    "role": "bot", 
                    "text": f"Saya telah mengenali transaksi berikut:\n\nTanggal: {parsed_txn['date']}\nJumlah: Rp {parsed_txn['amount']:,.2f}\nTipe: {parsed_txn['type']}\nKategori: {parsed_txn['category']}\nCatatan: {parsed_txn['note']}{reasoning_text}\n\nApakah Anda ingin menyimpannya?"
                })
                
                # Store parsed transaction for confirmation
                st.session_state.pending_transaction = parsed_txn
            else:
                # It's just a conversation, respond naturally
                response = gemini_client.generate_friendly_response(user_input)
                st.session_state.chat_history.append({
                    "role": "bot", 
                    "text": response
                })
        except Exception as e:
            st.session_state.chat_history.append({
                "role": "bot", 
                "text": f"Maaf, saya tidak dapat memproses permintaan Anda. Error: {str(e)}"
            })
            add_debug(f"Error processing request: {e}")

def main():
    # Custom CSS for better UI
    st.set_page_config(
        page_title="AI Gemini Finance Chatbot", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Add custom CSS
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 1rem;
        }
        .sub-header {
            font-size: 1.5rem;
            color: #2ca02c;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
        }
        .success-message {
            padding: 1rem;
            background-color: #d4edda;
            border-radius: 0.5rem;
            color: #155724;
            margin: 1rem 0;
        }
        .error-message {
            padding: 1rem;
            background-color: #f8d7da;
            border-radius: 0.5rem;
            color: #721c24;
            margin: 1rem 0;
        }
        .info-message {
            padding: 1rem;
            background-color: #d1ecf1;
            border-radius: 0.5rem;
            color: #0c5460;
            margin: 1rem 0;
        }
        .chat-container {
            background-color: #f8f9fa;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .user-message {
            background-color: #e3f2fd;
            padding: 0.5rem 1rem;
            border-radius: 1rem 1rem 0 1rem;
            margin-bottom: 0.5rem;
            max-width: 80%;
        }
        .bot-message {
            background-color: #e8f5e9;
            padding: 0.5rem 1rem;
            border-radius: 1rem 1rem 1rem 0;
            margin-bottom: 0.5rem;
            max-width: 80%;
            margin-left: auto;
        }
        .transaction-card {
            background-color: white;
            border-radius: 0.5rem;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        }
        .category-food { color: #ff7f0e; }
        .category-transport { color: #1f77b4; }
        .category-shopping { color: #9467bd; }
        .category-bills { color: #d62728; }
        .category-entertainment { color: #8c564b; }
        .category-health { color: #e377c2; }
        .category-education { color: #7f7f7f; }
        .category-income { color: #2ca02c; }
        .category-uncategorized { color: #17becf; }
        .clear-chat-btn {
            background-color: #dc3545;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 0.25rem;
            cursor: pointer;
            margin-top: 0.5rem;
        }
        .action-buttons {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.5rem;
        }
        .edit-form {
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-top: 1rem;
        }
        .query-examples {
            background-color: #f8f9fa;
            border-radius: 0.5rem;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .example-query {
            background-color: #e9ecef;
            border-radius: 0.25rem;
            padding: 0.5rem;
            margin: 0.25rem 0;
            cursor: pointer;
            text-align: left;
            border: none;
            width: 100%;
        }
        .example-query:hover {
            background-color: #dee2e6;
        }
    </style>
    """, unsafe_allow_html=True)
    
    initialize_state()

    # App header
    st.markdown('<h1 class="main-header">💰 AI Gemini Finance Chatbot</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #6c757d;">Masukkan pesan natural atau tambah transaksi manual. Aplikasi akan menyimpan ke Google Sheets.</p>', unsafe_allow_html=True)

    # Sidebar: settings
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        st.text_input("Path to Google Service Account JSON", value=GOOGLE_SHEETS_JSON, key="sa_path")
        st.text_input("Spreadsheet ID", value=SPREADSHEET_ID or "", key="spreadsheet_id_input")
        st.text_input("Gemini API Key", value=GEMINI_API_KEY or "", type="password", key="gemini_api_key")
        
        st.markdown("### Debug Options")
        debug_mode = st.checkbox("Enable debug mode", value=st.session_state.debug_mode)
        st.session_state.debug_mode = debug_mode
        
        if debug_mode and st.button("Show log file"):
            try:
                with open(LOG_FILENAME, "r", encoding="utf-8") as f:
                    st.code(f.read()[-10000:])  # show tail
            except Exception as e:
                st.error(f"Cannot read log file: {e}")

    # Gemini client
    gemini_api_key = st.session_state.get("gemini_api_key")
    if not gemini_api_key:
        st.error("Gemini API Key is required. Please provide it in the sidebar.")
        return
    
    gemini_client = GeminiClient(api_key=gemini_api_key)

    # Sheets client (connect lazily to avoid failures on load)
    sheets_client = None
    data_analyzer = None
    sa_path = st.session_state.get("sa_path")
    spreadsheet_id_input = st.session_state.get("spreadsheet_id_input")
    if sa_path and spreadsheet_id_input:
        try:
            sheets_client = SheetsClient(service_account_json=sa_path, spreadsheet_id=spreadsheet_id_input, sheet_name=SHEET_NAME)
            data_analyzer = DataAnalyzer(sheets_client)
            add_debug("Successfully connected to Google Sheets")
        except Exception as e:
            st.warning(f"Cannot connect to Google Sheets: {e}")
            add_debug(f"Sheets connection failed: {e}")
            sheets_client = None

    # Chat interface
    st.markdown('<h2 class="sub-header">💬 Chat Interface</h2>', unsafe_allow_html=True)
    
    # Clear chat button
    col1, col2 = st.columns([1, 9])
    with col1:
        if st.button("Bersihkan Chat", type="secondary"):
            clear_chat()
            st.rerun()
    
    # Example queries
    if data_analyzer:
        st.markdown('<div class="query-examples">', unsafe_allow_html=True)
        st.markdown("### Contoh Pertanyaan Data:")
        
        example_queries = [
            "Berapa total pengeluaran saya bulan ini?",
            "Apa kategori pengeluaran terbesar saya?",
            "Berapa pengeluaran saya untuk makanan bulan ini?",
            "Tunjukkan transaksi terkait 'transport'",
            "Berapa pemasukan vs pengeluaran saya 3 bulan terakhir?",
            "Apa saja transaksi terbesar saya?"
        ]
        
        for query in example_queries:
            if st.button(query, key=f"example_{query}"):
                st.session_state.chat_history.append({"role": "user", "text": query})
                # Process the query immediately
                process_user_input(query, gemini_client, data_analyzer)
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Display chat history
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.chat_history:
            if message["role"] == "user":
                st.markdown(f'<div class="user-message">{message["text"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="bot-message">{message["text"]}</div>', unsafe_allow_html=True)
    
    # Chat input
    user_input = st.text_input("Ketik perintah, deskripsi pengeluaran/pemasukan, atau pertanyaan tentang data Anda", key="user_input")
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Kirim", type="primary"):
            if not user_input:
                st.warning("Masukkan teks dulu.")
            else:
                st.session_state.chat_history.append({"role": "user", "text": user_input})
                # Process the input
                process_user_input(user_input, gemini_client, data_analyzer)
                st.rerun()
    
    # Confirm transaction button
    if "pending_transaction" in st.session_state:
        with col2:
            if st.button("Simpan Transaksi", type="secondary"):
                if not sheets_client:
                    st.error("Google Sheets belum terkonfigurasi atau gagal koneksi.")
                else:
                    try:
                        sheets_client.append_transaction(st.session_state.pending_transaction)
                        st.markdown('<div class="success-message">Transaksi berhasil disimpan! ✅</div>', unsafe_allow_html=True)
                        st.session_state.chat_history.append({
                            "role": "bot", 
                            "text": "Transaksi berhasil disimpan ke Google Sheets!"
                        })
                        del st.session_state.pending_transaction
                        st.rerun()
                    except Exception as e:
                        st.markdown(f'<div class="error-message">Gagal menyimpan: {e}</div>', unsafe_allow_html=True)
                        add_debug(f"Error saving transaction: {e}")
    
    st.markdown("---")
    
    # Manual entry form
    st.markdown('<h2 class="sub-header">📝 Tambah Transaksi Manual</h2>', unsafe_allow_html=True)
    
    with st.form("manual_txn"):
        col1, col2, col3 = st.columns(3)
        with col1:
            date_in = st.date_input("Tanggal", value=datetime.now().date())
            category_in = st.selectbox("Kategori", ["food", "transport", "shopping", "bills", "entertainment", "health", "education", "income", "uncategorized"])
        with col2:
            amount_in = st.text_input("Jumlah (contoh: 50k, 50000)", value="")
            type_in = st.selectbox("Tipe", ["expense", "income"])
        with col3:
            note_in = st.text_area("Catatan / Deskripsi", height=100)
        
        submitted = st.form_submit_button("Tambah & Simpan", type="primary")
        if submitted:
            try:
                amount_val = parse_amount(amount_in)
                txn = {
                    "date": date_in.isoformat(),
                    "amount": amount_val,
                    "type": type_in,
                    "category": normalize_category(category_in),
                    "note": note_in
                }
                add_debug(f"Manual transaction: {txn}")
                
                if not sheets_client:
                    st.markdown('<div class="error-message">Google Sheets belum terkonfigurasi atau gagal koneksi.</div>', unsafe_allow_html=True)
                else:
                    sheets_client.append_transaction(txn)
                    st.markdown('<div class="success-message">Transaksi berhasil disimpan ke Google Sheets! ✅</div>', unsafe_allow_html=True)
            except Exception as e:
                st.markdown(f'<div class="error-message">Gagal menambahkan transaksi: {e}</div>', unsafe_allow_html=True)
                add_debug(f"Error adding manual transaction: {e}")

    st.markdown("---")
    
    # Show recent transactions & analytics
    st.markdown('<h2 class="sub-header">📊 Riwayat & Ringkasan</h2>', unsafe_allow_html=True)
    
    if sheets_client:
        try:
            df = sheets_client.get_transactions_df()
            if df.empty:
                st.markdown('<div class="info-message">Belum ada transaksi.</div>', unsafe_allow_html=True)
            else:
                # Summary statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_income = df[df['type'] == 'income']['amount'].sum()
                    st.metric("Total Pemasukan", f"Rp {format_amount(total_income)}")
                with col2:
                    total_expense = df[df['type'] == 'expense']['amount'].sum()
                    st.metric("Total Pengeluaran", f"Rp {format_amount(total_expense)}")
                with col3:
                    balance = total_income - total_expense
                    st.metric("Saldo", f"Rp {format_amount(balance)}")
                with col4:
                    transaction_count = len(df)
                    st.metric("Jumlah Transaksi", f"{transaction_count}")
                
                # Tabs for different views
                tab1, tab2, tab3 = st.tabs(["📋 Data Tabel", "📈 Visualisasi", "🔍 Analisis"])
                
                with tab1:
                    # Create a copy of the dataframe for display (without timestamp)
                    display_df = df.copy().drop(columns=['timestamp'], errors='ignore')
                    
                    # Add row numbers for selection (starting from 2 to account for header in Google Sheets)
                    display_df = display_df.reset_index(drop=True)
                    display_df.index = display_df.index + 2  # +2 because Google Sheets rows start at 1 and header is at row 1
                    
                    # Display the dataframe with selection
                    st.markdown("### Pilih transaksi untuk diedit atau dihapus:")
                    selected_rows = st.dataframe(
                        display_df.sort_values(by='date', ascending=False),
                        use_container_width=True,
                        hide_index=True,
                        selection_mode="single-row",
                        on_select="rerun",
                        key="data_selection"
                    )
                    
                    # Get selected row index
                    selected_row_index = None
                    if selected_rows and selected_rows["selection"]["rows"]:
                        selected_row_index = selected_rows["selection"]["rows"][0] + 2  # Convert to Google Sheets row index
                    
                    # Action buttons
                    if selected_row_index:
                        st.markdown('<div class="action-buttons">', unsafe_allow_html=True)
                        col_edit, col_delete = st.columns(2)
                        with col_edit:
                            if st.button("✏️ Edit", key="edit_button"):
                                st.session_state.edit_mode = True
                                st.session_state.edit_row_index = selected_row_index
                                st.rerun()
                        with col_delete:
                            if st.button("🗑️ Hapus", key="delete_button"):
                                try:
                                    sheets_client.delete_transaction(selected_row_index)
                                    st.markdown('<div class="success-message">Transaksi berhasil dihapus! ✅</div>', unsafe_allow_html=True)
                                    st.rerun()
                                except Exception as e:
                                    st.markdown(f'<div class="error-message">Gagal menghapus: {e}</div>', unsafe_allow_html=True)
                                    add_debug(f"Error deleting transaction: {e}")
                        st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Edit form
                    if st.session_state.edit_mode and st.session_state.edit_row_index:
                        st.markdown('<div class="edit-form">', unsafe_allow_html=True)
                        st.markdown("### Edit Transaksi")
                        
                        # Get the row data
                        row_data = df.iloc[st.session_state.edit_row_index - 2]  # -2 because of header and 0-based index
                        
                        with st.form("edit_txn"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                edit_date = st.date_input("Tanggal", value=pd.to_datetime(row_data['date']).date())
                                edit_category = st.selectbox(
                                    "Kategori", 
                                    ["food", "transport", "shopping", "bills", "entertainment", "health", "education", "income", "uncategorized"],
                                    index=["food", "transport", "shopping", "bills", "entertainment", "health", "education", "income", "uncategorized"].index(row_data['category']) if row_data['category'] in ["food", "transport", "shopping", "bills", "entertainment", "health", "education", "income", "uncategorized"] else 0
                                )
                            with col2:
                                edit_amount = st.text_input("Jumlah", value=str(row_data['amount']))
                                edit_type = st.selectbox(
                                    "Tipe", 
                                    ["expense", "income"],
                                    index=0 if row_data['type'] == 'expense' else 1
                                )
                            with col3:
                                edit_note = st.text_area("Catatan / Deskripsi", value=row_data['note'], height=100)
                            
                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.form_submit_button("Simpan Perubahan", type="primary"):
                                    try:
                                        amount_val = parse_amount(edit_amount)
                                        updated_txn = {
                                            "date": edit_date.isoformat(),
                                            "amount": amount_val,
                                            "type": edit_type,
                                            "category": normalize_category(edit_category),
                                            "note": edit_note
                                        }
                                        sheets_client.update_transaction(st.session_state.edit_row_index, updated_txn)
                                        st.markdown('<div class="success-message">Transaksi berhasil diperbarui! ✅</div>', unsafe_allow_html=True)
                                        st.session_state.edit_mode = False
                                        st.session_state.edit_row_index = None
                                        st.rerun()
                                    except Exception as e:
                                        st.markdown(f'<div class="error-message">Gagal memperbarui: {e}</div>', unsafe_allow_html=True)
                                        add_debug(f"Error updating transaction: {e}")
                            with col_cancel:
                                if st.form_submit_button("Batal"):
                                    st.session_state.edit_mode = False
                                    st.session_state.edit_row_index = None
                                    st.rerun()
                        
                        st.markdown('</div>', unsafe_allow_html=True)
                
                with tab2:
                    # Category breakdown
                    cat_sum = df.groupby("category")["amount"].sum().sort_values(ascending=False)
                    
                    # Create subplots
                    fig = make_subplots(
                        rows=2, cols=2,
                        subplot_titles=("Pengeluaran per Kategori", "Pemasukan vs Pengeluaran", "Transaksi per Hari", "Distribusi Kategori"),
                        specs=[[{"type": "bar"}, {"type": "pie"}],
                               [{"type": "scatter"}, {"type": "bar"}]]
                    )
                    
                    # Expense by category
                    expense_by_cat = df[df['type'] == 'expense'].groupby("category")["amount"].sum().sort_values(ascending=False)
                    fig.add_trace(
                        go.Bar(x=expense_by_cat.index, y=expense_by_cat.values, name="Pengeluaran"),
                        row=1, col=1
                    )
                    
                    # Income vs Expense
                    fig.add_trace(
                        go.Pie(labels=["Pemasukan", "Pengeluaran"], 
                               values=[total_income, total_expense],
                               hole=0.3),
                        row=1, col=2
                    )
                    
                    # Transactions per day
                    daily_count = df.groupby('date').size().reset_index(name='count')
                    # Convert date to string for proper serialization
                    daily_count['date'] = daily_count['date'].astype(str)
                    fig.add_trace(
                        go.Scatter(x=daily_count['date'], y=daily_count['count'], mode='lines+markers', name="Transaksi/Hari"),
                        row=2, col=1
                    )
                    
                    # Category distribution
                    fig.add_trace(
                        go.Bar(x=cat_sum.index, y=cat_sum.values, name="Total per Kategori"),
                        row=2, col=2
                    )
                    
                    fig.update_layout(height=800, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                
                with tab3:
                    # Monthly trend - FIXED: Convert to datetime instead of Period
                    df['date'] = pd.to_datetime(df['date'])
                    # Use the first day of each month instead of Period objects
                    df['month'] = df['date'].dt.to_period('M').dt.to_timestamp()
                    monthly_summary = df.groupby(['month', 'type'])['amount'].sum().unstack().fillna(0)
                    
                    st.markdown("### Tren Bulanan")
                    fig = px.line(
                        monthly_summary.reset_index(), 
                        x='month', 
                        y=['expense', 'income'],
                        labels={'value': 'Jumlah (Rp)', 'month': 'Bulan'},
                        title="Pemasukan vs Pengeluaran per Bulan"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Top spending categories
                    st.markdown("### Kategori Pengeluaran Teratas")
                    top_expense = df[df['type'] == 'expense'].groupby("category")["amount"].sum().sort_values(ascending=False).head(10)
                    fig = px.bar(
                        x=top_expense.values, 
                        y=top_expense.index,
                        orientation='h',
                        labels={'x': 'Jumlah (Rp)', 'y': 'Kategori'},
                        title="10 Kategori Pengeluaran Teratas"
                    )
                    st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.markdown(f'<div class="error-message">Gagal memuat data: {e}</div>', unsafe_allow_html=True)
            add_debug(f"Error loading data: {e}")
    else:
        st.markdown('<div class="info-message">Hubungkan Google Sheets terlebih dahulu melalui Settings di sidebar.</div>', unsafe_allow_html=True)

    # Debug logs (if enabled)
    if st.session_state.debug_mode:
        st.markdown("---")
        st.markdown('<h2 class="sub-header">🐛 Debug Log</h2>', unsafe_allow_html=True)
        for line in st.session_state.debug_logs[-50:]:
            st.text(line)

    st.markdown("---")
    st.markdown('<p style="text-align: center; color: #6c757d;">Mabot : AI Gemini Finance Chatbot © 2025</p>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()