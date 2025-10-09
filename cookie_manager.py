"""
Cookie management utilities using streamlit-cookies-manager.
Versi yang diperbaiki untuk production di Streamlit Cloud.
"""

import streamlit as st
import logging
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController

logger = logging.getLogger("finance_chatbot")

# --- PERUBAHAN KRUSIAL ---
# Inisialisasi controller HANYA SEKALI di level modul (paling atas).
# Ini harus dilakukan sebelum fungsi manapun dipanggil.
try:
    controller = CookieController()
    logger.info("CookieController initialized successfully at module level.")
except Exception as e:
    logger.error(f"FATAL: Failed to initialize CookieController: {e}")
    # Jika controller gagal diinisialisasi, aplikasi tidak bisa berjalan dengan cookie.
    # Set ke None untuk mencegah crash dan menangani error di tempat lain.
    controller = None

def get_session_token():
    """Retrieves the session token from the cookie."""
    controller = CookieController()
    if not controller:
        logger.error("CookieController is not available.")
        return None
    try:
        token = controller.get('session_token')
        if token:
            logger.info("Session token found in cookie.")
        else:
            logger.info("No session token found in cookie.")
        return token
    except Exception as e:
        logger.error(f"Error getting session token: {e}")
        return None

def set_session_token(token: str):
    """Sets the session token in the cookie with expiration."""
    controller = CookieController()
    if not controller:
        logger.error("CookieController is not available.")
        return False
    try:
        controller.set('session_token', token)
        logger.info(f"Session token saved to cookie, expires at.")
        return True
    except Exception as e:
        logger.error(f"Could not set session token: {e}")
        return False

def delete_session_token():
    """Deletes the session token from the cookie."""
    if not controller:
        logger.error("CookieController is not available.")
        return False
    try:
        controller.remove('session_token')
        logger.info("Session token deleted from cookie.")
        return True
    except Exception as e:
        logger.error(f"Could not delete session token: {e}")
        return False

# Fungsi get_cookies tidak lagi diperlukan jika kita menggunakan controller langsung.
# Tapi biarkan saja jika ada bagian lain yang menggunakannya.
def get_cookies():
    """Returns all cookies from the controller."""
    if not controller:
        return {}
    try:
        return controller.getAll()
    except Exception as e:
        logger.error(f"Error getting all cookies: {e}")
        return {}