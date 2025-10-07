"""
Data analysis tools for the finance chatbot.
"""

import logging
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger("finance_chatbot")

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