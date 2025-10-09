"""
Cookie management utilities using streamlit-cookies-manager.
"""

import streamlit as st
import logging
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController

logger = logging.getLogger("finance_chatbot")

def get_cookie_controller():
    """Returns a properly initialized cookie controller instance."""
    if 'cookie_controller' not in st.session_state:
        st.session_state.cookie_controller = CookieController()
    return st.session_state.cookie_controller

def get_cookies():
    """Returns all cookies from the controller."""
    controller = get_cookie_controller()
    return controller.getAll()

def get_session_token():
    """Retrieves the session token from the cookie."""
    try:
        controller = get_cookie_controller()
        token = controller.get('session_token')
        if token:
            logger.debug("Session token found in cookie.")
        else:
            logger.debug("No session token found in cookie.")
        return token
    except Exception as e:
        logger.error(f"Error getting session token: {e}")
        return None

def set_session_token(token: str, expires_days: int = 30):
    """Sets the session token in the cookie with expiration."""
    try:
        controller = get_cookie_controller()
        # Set expiration date
        expires_at = datetime.now() + timedelta(days=expires_days)
        
        # Set cookie with expiration
        controller.set(
            'session_token', 
            token,
            expires_at=expires_at
        )
        logger.info(f"Session token saved to cookie, expires at {expires_at}.")
        return True
    except Exception as e:
        logger.error(f"Could not set session token: {e}")
        return False

def delete_session_token():
    """Deletes the session token from the cookie."""
    try:
        controller = get_cookie_controller()
        controller.remove('session_token')
        logger.info("Session token deleted from cookie.")
        return True
    except Exception as e:
        logger.error(f"Could not delete session token: {e}")
        return False