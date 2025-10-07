"""
Main Streamlit app for the Mabot: AI Gemini Finance Chatbot.
"""
import os
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from langchain.memory import ConversationBufferMemory
from auth import show_login_page, logout, check_session
from utils import extract_spreadsheet_id_from_url
from sheets_client import SheetsClient

# Import our modules
from config import (
    GOOGLE_SHEETS_JSON, SHEET_NAME, GEMINI_API_KEY, 
    logger, LOG_FILENAME, DATABASE_URL, SECRET_KEY, TEMPLATE_SPREADSHEET_URL
)
from utils import parse_amount, normalize_category, format_amount, paginate_dataframe, extract_spreadsheet_id_from_url
from sheets_client import SheetsClient
from gemini_client import GeminiClient
from data_analyzer import DataAnalyzer
from database import Database
from auth import show_login_page, logout, check_password

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
    if "current_page" not in st.session_state:
        st.session_state.current_page = 1
    if "memory" not in st.session_state:
        st.session_state.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "db" not in st.session_state:
        if DATABASE_URL:
            st.session_state.db = Database(DATABASE_URL)
        else:
            st.session_state.db = None

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
    Process user input and generate appropriate response with contextual memory.
    """
    if not user_input:
        return
    
    add_debug(f"User input: {user_input}")
    
    with st.spinner("Sedang memproses..."):
        try:
            # Cek apakah ada transaksi yang sedang menunggu konfirmasi
            has_pending = "pending_transaction" in st.session_state
            
            # --- LOGIKA BARU DIMULAI DI SINI ---
            if has_pending:
                # Ada transaksi pending, gunakan konteks
                pending_context = st.session_state.pending_transaction
                parsed_result = gemini_client.parse_transaction_with_context(user_input, pending_context)
                
                intent = parsed_result.get("intent", "new_transaction")
                add_debug(f"Intent: {intent}")
                
                if intent == "update_transaction":
                    # AI menganggap ini adalah pembaruan
                    st.session_state.pending_transaction = parsed_result
                    reasoning = parsed_result.get("reasoning", "")
                    
                    st.session_state.chat_history.append({
                        "role": "bot", 
                        "text": f"Baik, saya perbarui transaksinya. Berikut detailnya:\n\nTanggal: {parsed_result['date']}\nJumlah: Rp {parsed_result['amount']:,.2f}\nTipe: {parsed_result['type']}\nKategori: {parsed_result['category']}\nCatatan: {parsed_result['note']}\n\nAlasan: {reasoning}\n\nApakah Anda ingin menyimpannya?"
                    })
                elif intent == "new_transaction":
                    # AI menganggap ini transaksi baru, ganti yang lama
                    st.session_state.chat_history.append({
                        "role": "bot", 
                        "text": "Oke, saya anggap ini transaksi baru. Transaksi sebelumnya saya abaikan ya."
                    })
                    st.session_state.pending_transaction = parsed_result
                    st.session_state.chat_history.append({
                        "role": "bot", 
                        "text": f"Saya telah mengenali transaksi berikut:\n\nTanggal: {parsed_result['date']}\nJumlah: Rp {parsed_result['amount']:,.2f}\nTipe: {parsed_result['type']}\nKategori: {parsed_result['category']}\nCatatan: {parsed_result['note']}\n\nApakah Anda ingin menyimpannya?"
                    })
                else: # conversation
                    response = gemini_client.generate_friendly_response(user_input)
                    st.session_state.chat_history.append({
                        "role": "bot", 
                        "text": response
                    })
            else:
                # Tidak ada transaksi pending, gunakan logika lama
                is_transaction, is_data_query, reasoning, friendly_response = gemini_client.is_transaction(user_input)
                add_debug(f"Is transaction: {is_transaction}, Is data query: {is_data_query}, Reasoning: {reasoning}")
                
                if is_data_query and data_analyzer:
                    data_summary = data_analyzer.get_data_summary()
                    response = gemini_client.analyze_data_query(user_input, data_summary)
                    st.session_state.chat_history.append({
                        "role": "bot", 
                        "text": response
                    })
                elif is_transaction:
                    parsed_txn = gemini_client.parse_transaction(user_input)
                    add_debug(f"Parsed transaction: {parsed_txn}")
                    
                    reasoning = parsed_txn.get("reasoning", "")
                    if reasoning:
                        reasoning_text = f"\n\nPerhitungan: {reasoning}"
                    else:
                        reasoning_text = ""
                    
                    st.session_state.chat_history.append({
                        "role": "bot", 
                        "text": f"Saya telah mengenali transaksi berikut:\n\nTanggal: {parsed_txn['date']}\nJumlah: Rp {parsed_txn['amount']:,.2f}\nTipe: {parsed_txn['type']}\nKategori: {parsed_txn['category']}\nCatatan: {parsed_txn['note']}{reasoning_text}\n\nApakah Anda ingin menyimpannya?"
                    })
                    
                    st.session_state.pending_transaction = parsed_txn
                else:
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

def show_spreadsheet_setup():
    """Display the spreadsheet setup page with user-defined names."""
    st.title("Setup Google Sheets")
    
    st.markdown("""
    Untuk menggunakan aplikasi ini, Anda perlu menghubungkan ke Google Sheets Anda.
    Ikuti langkah-langkah berikut:
    """)
    
    # Step 1: Create a copy of the template
    st.markdown("### Langkah 1: Buat Salinan Template")
    st.markdown(f"""
    1. Buka [template spreadsheet]({TEMPLATE_SPREADSHEET_URL}) di tab baru
    2. Klik File -> Buat salinan
    3. Beri nama spreadsheet Anda
    4. Pilih folder Google Drive Anda
    5. Klik OK
    """)
    
    # Step 2: Share the spreadsheet with the service account
    st.markdown("### Langkah 2: Bagikan Spreadsheet dengan Service Account")
    st.markdown("""
    1. Buka spreadsheet yang baru Anda buat
    2. Klik tombol Bagikan (Share) di kanan atas
    3. Tambahkan email service account: mabot-service-account@mabot-project.iam.gserviceaccount.com
    4. Berikan izin Editor
    5. Klik Kirim
    """)
    
    # Step 3: Get the spreadsheet URL and name
    st.markdown("### Langkah 3: Masukkan Detail Spreadsheet")
    st.markdown("""
    Salin URL spreadsheet Anda dari browser dan beri nama untuk memudahkan identifikasi.
    """)
    
    with st.form("spreadsheet_form"):
        spreadsheet_url = st.text_input("URL Spreadsheet", placeholder="https://docs.google.com/spreadsheets/d/...")
        # --- PERUBAAN: User memberi nama sendiri ---
        spreadsheet_name = st.text_input("Nama Spreadsheet (untuk identifikasi)", placeholder="Contoh: Keuangan Pribadi 2025")
        submitted = st.form_submit_button("Hubungkan Spreadsheet")
        
        if submitted:
            if not spreadsheet_url or not spreadsheet_name:
                st.error("Silakan masukkan URL dan nama spreadsheet.")
            else:
                spreadsheet_id = extract_spreadsheet_id_from_url(spreadsheet_url)
                if not spreadsheet_id:
                    st.error("URL spreadsheet tidak valid. Pastikan Anda menyalin URL yang benar.")
                else:
                    # Simpan ke database dengan nama yang diberikan user
                    db = st.session_state.get("db")
                    user = st.session_state.get("user")
                    if db and user:
                        if db.add_spreadsheet(user['id'], spreadsheet_id, spreadsheet_name):
                            st.success(f"Spreadsheet '{spreadsheet_name}' berhasil dihubungkan!")
                            st.session_state["spreadsheet_id"] = spreadsheet_id
                            st.rerun()
                        else:
                            st.error("Gagal menghubungkan spreadsheet. Silakan coba lagi.")
                    else:
                        st.error("Terjadi kesalahan. Silakan coba lagi.")
    
    # Show existing spreadsheets
    db = st.session_state.get("db")
    user = st.session_state.get("user")
    if db and user:
        spreadsheets = db.get_user_spreadsheets(user['id'])
        if spreadsheets:
            st.markdown("### Spreadsheet Anda")
            for sheet in spreadsheets:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"- **{sheet['spreadsheet_name']}**")
                with col2:
                    if st.button("Gunakan", key=f"use_sheet_{sheet['id']}"):
                        st.session_state["spreadsheet_id"] = sheet['spreadsheet_id']
                        st.rerun()
                # --- PERBAIKAN DIMULAI DI SINI ---
                with col3:
                    if st.button("Hapus", key=f"delete_sheet_{sheet['id']}"):
                        if st.session_state.get("spreadsheet_id") == sheet['spreadsheet_id']:
                            st.warning("Anda sedang menggunakan spreadsheet ini. Pilih spreadsheet lain sebelum menghapus.")
                        else:
                            # Hanya setel flag konfirmasi, jangan lakukan apa-apa lagi
                            st.session_state[f"confirm_delete_{sheet['id']}"] = True
                            st.rerun()

                # Tampilkan dialog konfirmasi jika flag-nya aktif
                if st.session_state.get(f"confirm_delete_{sheet['id']}", False):
                    with st.container(): # Bungkus dalam container untuk tata letak yang lebih baik
                        st.warning(f"⚠️ Anda yakin ingin menghapus spreadsheet '{sheet['spreadsheet_name']}'? Tindakan ini tidak dapat dibatalkan.")
                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button("Ya, Hapus", key=f"confirm_yes_{sheet['id']}", type="primary"):
                                # --- LOGIKA HAPUS YANG SEBENARNYA ADA DI SINI ---
                                if db.delete_spreadsheet(user['id'], sheet['spreadsheet_id']):
                                    st.success(f"Spreadsheet '{sheet['spreadsheet_name']}' telah dihapus.")
                                    # Hapus flag konfirmasi dari session state
                                    del st.session_state[f"confirm_delete_{sheet['id']}"]
                                    st.rerun()
                                else:
                                    st.error("Gagal menghapus spreadsheet. Silakan coba lagi.")
                        with col_cancel:
                            if st.button("Batal", key=f"confirm_no_{sheet['id']}"):
                                # Hapus flag konfirmasi dari session state
                                del st.session_state[f"confirm_delete_{sheet['id']}"]
                                st.rerun()

def main():
    # Custom CSS for better UI
    st.set_page_config(
        page_title="Mabot: AI Gemini Finance Chatbot", 
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
    
    # Cek sesi dan setup spreadsheet
    if not check_session():
        show_login_page()
        return
    
    # Check if user has set up a spreadsheet
    if "spreadsheet_id" not in st.session_state:
        show_spreadsheet_setup()
        return
    
    # App header
    st.markdown('<h1 class="main-header">💰Mabot: AI Gemini Finance Chatbot</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #6c757d;">Masukkan pesan natural atau tambah transaksi manual. Aplikasi akan menyimpan ke Google Sheets.</p>', unsafe_allow_html=True)

    # Sidebar: settings
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # User info
        user = st.session_state.get("user")
        if user:
            st.markdown(f"**Logged in as:** {user['username']}")
            if st.button("Logout"):
                logout()
        
        st.markdown("---")
        
        # Gemini API Key
        # gemini_api_key = st.text_input("Gemini API Key", value=GEMINI_API_KEY or "", type="password", key="gemini_api_key")
        gemini_api_key = GEMINI_API_KEY
        # st.markdown("---")
        
        # Spreadsheet info
        spreadsheet_id = st.session_state.get("spreadsheet_id")
        if spreadsheet_id:
            st.markdown(f"**Spreadsheet ID:** {spreadsheet_id[:10]}...")
            if st.button("Change Spreadsheet"):
                del st.session_state["spreadsheet_id"]
                st.rerun()
        
        # st.markdown("---")
        
        # st.markdown("### Debug Options")
        # debug_mode = st.checkbox("Enable debug mode", value=st.session_state.debug_mode)
        # st.session_state.debug_mode = debug_mode
        
        # if debug_mode and st.button("Show log file"):
        #     try:
        #         with open(LOG_FILENAME, "r", encoding="utf-8") as f:
        #             st.code(f.read()[-10000:])  # show tail
        #     except Exception as e:
        #         st.error(f"Cannot read log file: {e}")

    # Gemini client
    # if not gemini_api_key:
    #     st.error("Gemini API Key is required. Please provide it in the sidebar.")
    #     return
    
    gemini_client = GeminiClient(api_key=gemini_api_key)

    # Sheets client (connect lazily to avoid failures on load)
    sheets_client = None
    data_analyzer = None
    spreadsheet_id = st.session_state.get("spreadsheet_id")
    
    # Kembali menggunakan GOOGLE_SHEETS_JSON
    if GOOGLE_SHEETS_JSON and spreadsheet_id:
        try:
            sheets_client = SheetsClient(
                credentials_string=GOOGLE_SHEETS_JSON, 
                spreadsheet_id=spreadsheet_id, 
                sheet_name=SHEET_NAME
            )
            data_analyzer = DataAnalyzer(sheets_client)
            add_debug("Successfully connected to Google Sheets")
        except Exception as e:
            st.warning(f"Cannot connect to Google Sheets: {e}")
            add_debug(f"Sheets connection failed: {e}")
            sheets_client = None
    else:
        if not GOOGLE_SHEETS_JSON:
            st.error("Google Sheets credentials not found. Please set GOOGLE_SHEETS_JSON in your .env file.")
    

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
                    # Pagination settings
                    page_size = st.slider("Jumlah data per halaman", min_value=5, max_value=50, value=10, step=5)
                    
                    # Get total number of pages
                    total_rows = len(df)
                    total_pages = max(1, (total_rows + page_size - 1) // page_size)
                    
                    # Fix: ensure current_page is valid
                    if "current_page" not in st.session_state:
                        st.session_state.current_page = 1
                    elif st.session_state.current_page > total_pages:
                        st.session_state.current_page = total_pages
                    elif st.session_state.current_page < 1:
                        st.session_state.current_page = 1
                    
                    # Page selection
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col1:
                        if st.button("⬅️ Halaman Sebelumnya", disabled=st.session_state.get("current_page", 1) <= 1):
                            st.session_state.current_page = max(1, st.session_state.get("current_page", 1) - 1)
                            st.rerun()
                    
                    with col2:
                        current_page = st.number_input(
                                            "Halaman",
                                            min_value=1,
                                            max_value=total_pages,
                                            value=min(st.session_state.get("current_page", 1), total_pages),
                                            step=1
                                        )
                        st.session_state.current_page = current_page
                    
                    with col3:
                        if st.button("Halaman Berikutnya ➡️", disabled=st.session_state.get("current_page", 1) >= total_pages):
                            st.session_state.current_page = min(total_pages, st.session_state.get("current_page", 1) + 1)
                            st.rerun()
                    
                    # Display page info
                    st.info(f"Menampilkan halaman {current_page} dari {total_pages} (Total {total_rows} transaksi)")
                    
                    # Get paginated data
                    paginated_df = paginate_dataframe(df, page_size, current_page)
                    
                    # Create a copy of the paginated dataframe for display (without timestamp)
                    display_df = paginated_df.copy().drop(columns=['timestamp'], errors='ignore')
                    
                    # Add row numbers for selection (starting from 2 to account for header in Google Sheets)
                    # We need to calculate the actual row indices in the original dataframe
                    start_idx = (current_page - 1) * page_size
                    display_df = display_df.reset_index(drop=True)
                    display_df.index = display_df.index + start_idx + 2  # +2 because Google Sheets rows start at 1 and header is at row 1
                    
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
                        # Convert the selected row index in the paginated view to the actual row index in the original dataframe
                        selected_row_in_page = selected_rows["selection"]["rows"][0]
                        selected_row_index = start_idx + selected_row_in_page + 2  # Convert to Google Sheets row index
                    
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
    st.markdown('<p style="text-align: center; color: #6c757d;">Mabot : AI Gemini Finance Chatbot 2025</p>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()