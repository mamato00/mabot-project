"""
Authentication and session management for the finance chatbot.
"""

import streamlit as st
import logging
from datetime import datetime, timedelta

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

def show_login_page():
    """Display the login page"""
    st.title("Login to Finance Chatbot")
    st.markdown("Please enter your credentials to access the application.")
    
    # Create login form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            # Check credentials against database
            db = st.session_state.get("db")
            if db:
                user = db.authenticate_user(username, password)
                if user:
                    st.session_state["user"] = user
                    st.session_state["logged_in"] = True
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            else:
                st.error("Database connection error. Please try again later.")
    
    # Show registration link
    st.markdown("---")
    st.markdown("Don't have an account? [Register here](#)")
    
    # Registration form
    with st.expander("Register a new account"):
        with st.form("register_form"):
            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email")
            new_password = st.text_input("Choose a password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
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
    """Log out the current user"""
    if "user" in st.session_state:
        del st.session_state["user"]
    if "logged_in" in st.session_state:
        del st.session_state["logged_in"]
    if "sheets_client" in st.session_state:
        del st.session_state["sheets_client"]
    if "data_analyzer" in st.session_state:
        del st.session_state["data_analyzer"]
    st.rerun()

def check_session():
    """Check for a valid session token and log the user in if found."""
    if "session_token" in st.session_state:
        token = st.session_state["session_token"]
        db = st.session_state.get("db")
        if db:
            user = db.validate_session(token)
            if user:
                st.session_state["user"] = user
                st.session_state["logged_in"] = True
                return True
            else:
                # Token is invalid or expired
                del st.session_state["session_token"]
                if "user" in st.session_state:
                    del st.session_state["user"]
                st.session_state["logged_in"] = False
                return False
    return False

def show_login_page():
    """Display the login page with session management."""
    st.title("Login to Finance Chatbot")
    st.markdown("Please enter your credentials to access the application.")
    
    # Create login form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        remember_me = st.checkbox("Remember me for 30 days")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            # Check credentials against database
            db = st.session_state.get("db")
            if db:
                user = db.authenticate_user(username, password)
                if user:
                    # Create session
                    session_token = db.create_session(user['id'], remember_me)
                    if session_token:
                        st.session_state["session_token"] = session_token
                        st.session_state["user"] = user
                        st.session_state["logged_in"] = True
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Failed to create session. Please try again.")
                else:
                    st.error("Invalid username or password")
            else:
                st.error("Database connection error. Please try again later.")
    
    # Show registration link
    st.markdown("---")
    st.markdown("Don't have an account? [Register here](#)")
    
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
    """Log out the current user by destroying the session."""
    if "session_token" in st.session_state:
        db = st.session_state.get("db")
        if db:
            db.delete_session(st.session_state["session_token"])
        del st.session_state["session_token"]
    
    if "user" in st.session_state:
        del st.session_state["user"]
    if "logged_in" in st.session_state:
        del st.session_state["logged_in"]
    if "sheets_client" in st.session_state:
        del st.session_state["sheets_client"]
    if "data_analyzer" in st.session_state:
        del st.session_state["data_analyzer"]
    if "spreadsheet_id" in st.session_state:
        del st.session_state["spreadsheet_id"]
        
    st.rerun()