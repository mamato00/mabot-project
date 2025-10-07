"""
Gemini client for the finance chatbot.
"""

import json
import logging
import re
from datetime import date
from typing import Dict, Any, Tuple

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage

from utils import parse_amount, normalize_category

logger = logging.getLogger("finance_chatbot")

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

    def is_transaction(self, text: str) -> Tuple[bool, bool, str, str]:
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
            raise Exception(f"Failed to parse transaction: {e}")

    def parse_transaction_with_context(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse transaction with context from a previous pending transaction.
        """
        today_str = date.today().isoformat()
        
        # Format context menjadi string yang mudah dibaca
        context_str = f"""
        Transaksi Sebelumnya yang Sedang Diproses:
        - Tanggal: {context.get('date', 'N/A')}
        - Jumlah: Rp {context.get('amount', 0):,.2f}
        - Tipe: {context.get('type', 'N/A')}
        - Kategori: {context.get('category', 'N/A')}
        - Catatan: {context.get('note', 'N/A')}
        """
        
        prompt = f"""
        Analisis teks pengguna berikut dalam konteks transaksi sebelumnya.
        
        {context_str}
        
        Teks Pengguna Baru: "{text}"
        
        Tugas Anda adalah memutuskan apakah teks baru ini:
        1. **Merupakan pembaruan** dari transaksi sebelumnya (misalnya, menambah biaya ongkir, mengubah jumlah, dll.).
        2. **Merupakan transaksi baru** yang sama sekali berbeda.
        3. Hanya percakapan biasa.
        
        Jika ini adalah pembaruan, hitung total baru dan gabungkan informasinya.
        Jika ini adalah transaksi baru, ekstrak informasinya seperti biasa.
        
        Return a JSON object with these keys:
        - intent: "update_transaction", "new_transaction", or "conversation"
        - date: transaction date in YYYY-MM-DD format
        - amount: numeric value without currency symbols (total if updated)
        - type: either "expense" or "income"
        - category: one of these categories: food, transport, shopping, bills, entertainment, health, education, income, or uncategorized
        - note: brief description of the transaction (combine if updated)
        - reasoning: brief explanation of your decision
        
        Only return valid JSON, nothing else.
        """
        
        try:
            response = self.generate(prompt, max_tokens=1024)
            logger.debug(f"Gemini with context raw response: {response}")
            
            # Clean up response to ensure it's valid JSON
            json_match = re.search(r'```json\n(.*?)\n```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response.strip()
            
            parsed = json.loads(json_str)
            
            # Normalize values only if it's a transaction
            if parsed.get("intent") in ["update_transaction", "new_transaction"]:
                if "amount" in parsed:
                    parsed["amount"] = parse_amount(str(parsed["amount"]))
                if "category" in parsed:
                    parsed["category"] = normalize_category(parsed.get("category"))
            
            return parsed
        except Exception as e:
            logger.exception("Failed to parse transaction with context")
            # Fallback to parsing without context if it fails
            logger.info("Falling back to parsing without context.")
            return self.parse_transaction(text)
        
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