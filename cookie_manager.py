"""
Cookie management utilities using streamlit-cookies-manager.
"""

import streamlit as st
import logging
import time
import os
from streamlit_cookies_controller import CookieController

logger = logging.getLogger("finance_chatbot")

cookieController = CookieController()
cookies = cookieController.getAll()

def get_cookies():
    """Returns the All cookie manager instance."""
    return cookies

def get_session_token():
    """Retrieves the session token from the cookie."""
    if cookieController:
        token = cookieController.get('session_token')
        if token:
            logger.debug("Session token found in cookie.")
        else:
            logger.debug("No session token found in cookie.")
        return token
    return None

def set_session_token(token: str):
    """Sets the session token in the cookie."""
    if cookieController:
        cookieController.set('session_token', token)
        logger.info("Session token saved to cookie.")
        return True
    else:
        logger.error("Could not set session token: Cookie controller not working.")
        return False

def delete_session_token():
    """Deletes the session token from the cookie."""
    if cookieController:
        cookieController.delete('session_token')
        logger.info("Session token deleted from cookie.")
        return True
    else:
        logger.error("Could not delete session token: Cookie manager not ready.")
        return False