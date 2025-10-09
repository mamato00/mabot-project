"""
Authentication and session management for the finance chatbot.
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
from cookie_manager import get_session_token, set_session_token, delete_session_token

logger = logging.getLogger("finance_chatbot")

def check_password():
    """Returns True if the user has a correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["username"] in st.secrets["passwords"] and st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password.
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show inputs for username + password.
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input("Username", on_change=password_entered, key="username")
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 User/password incorrect")
        return False
    else:
        # Password correct.
        return True

def check_session():
    """
    Checks for a valid session token from the browser cookie.
    If a valid token is found, it populates st.session_state.
    """
    # # 1. Cek apakah user sudah login di session state saat ini (untuk performa kalau diluar streamlit)
    # if st.session_state.get("logged_in", False):
    #     return True

    # 2. Jika belum, coba ambil token dari cookie
    token = get_session_token()
    logger.debug(f"token = {token}")

    if not token:
        logger.debug("No session token found in cookie.")
        return False

    db = st.session_state.get("db")
    if not db:
        logger.error("Database connection not found in session state.")
        return False

    try:
        user = db.validate_session(token)
        if user:
            # Token valid, login user dan simpan info di session state
            st.session_state["session_token"] = token
            st.session_state["user"] = user
            st.session_state["logged_in"] = True
            logger.info(f"User '{user['username']}' logged in via cookie.")
            return True
        else:
            # Token tidak valid (kedaluwarsa atau tidak ada di DB), hapus cookie
            logger.warning("Invalid token found in cookie. Deleting cookie.")
            delete_session_token()
            return False
    except Exception as e:
        logger.exception("An error occurred during session validation.")
        return False

def show_login_page():
    """Display the login page with session management."""
    st.title("Login to Finance Chatbot")
    st.markdown("Please enter your credentials to access the application.")
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("Remember me for 30 days")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            db = st.session_state.get("db")
            if db:
                user = db.authenticate_user(username, password)
                if user:
                    session_token = db.create_session(user['id'], remember_me)
                    if session_token:
                        if set_session_token(session_token):
                            message = "Login successful! You will be remembered on this browser."
                            if not remember_me:
                                message = "Login successful! You will be remembered for one day."
                            st.success(message)
                        else:
                            st.warning("Login successful, but we couldn't save your session for the next visit. You might need to log in again later.")
                        
                        st.rerun()
                        
                    else:
                        st.error("Failed to create session. Please try again.")
                else:
                    st.error("Invalid username or password")
            else:
                st.error("Database connection error. Please try again later.")
    
    # Show registration link
    st.markdown("---")
    st.markdown("Don't have an account? Register now!")
    
    # Registration form
    with st.expander("Register a new account"):
        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Choose a password", type="password", help="Password akan dipotong hingga 72 karakter.")
            confirm_password = st.text_input("Confirm password", type="password")
            
            if new_password and len(new_password.encode('utf-8')) > 72:
                st.warning("⚠️ Password Anda sangat panjang. Untuk keamanan, hanya 72 karakter pertama yang akan digunakan.")
            
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    db = st.session_state.get("db")
                    if db:
                        success, result = db.create_user(new_username, new_email, new_password)
                        if success:
                            st.success("Registration successful! You can now log in.")
                        else:
                            st.error(f"Registration failed: {result}")
                    else:
                        st.error("Database connection error. Please try again later.")

def logout():
    """Log out the current user by destroying the session and cookie."""
    # Hapus token dari cookie jika manager siap
    delete_session_token()
    
    # Hapus dari session state
    if "session_token" in st.session_state:
        del st.session_state["session_token"]
    if "user" in st.session_state:
        del st.session_state["user"]
    if "logged_in" in st.session_state:
        st.session_state["logged_in"] = False
        
    # Hapus state lainnya
    for key in ["sheets_client", "data_analyzer", "spreadsheet_id"]:
        if key in st.session_state:
            del st.session_state[key]
        
    st.rerun()