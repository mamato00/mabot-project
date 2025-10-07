"""
Database operations for user authentication and data management.
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets  # Untuk generate token yang aman

logger = logging.getLogger("finance_chatbot")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Database:
    def __init__(self, database_url):
        self.database_url = database_url
        self.connection = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        try:
            self.connection = psycopg2.connect(self.database_url)
            logger.info("Connected to database")
        except Exception as e:
            logger.exception("Failed to connect to database")
            raise
    
    def _create_tables(self):
        try:
            with self.connection.cursor() as cursor:
                # Create users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        username VARCHAR(50) UNIQUE NOT NULL,
                        email VARCHAR(100) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_login TIMESTAMP
                    )
                """)
                
                # Create user_spreadsheets table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_spreadsheets (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        spreadsheet_id VARCHAR(100) NOT NULL,
                        spreadsheet_name VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, spreadsheet_id)
                    )
                """)
                
                # --- TAMBAHKAN TABEL SESSIONS ---
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id SERIAL PRIMARY KEY,
                        token VARCHAR(255) UNIQUE NOT NULL,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                self.connection.commit()
                logger.info("Database tables created or verified")
        except Exception as e:
            logger.exception("Failed to create database tables")
            self.connection.rollback()
            raise
    
    def close(self):
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
    
    def create_user(self, username, email, password):
        try:
            with self.connection.cursor() as cursor:
                # Check if user already exists
                cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
                if cursor.fetchone():
                    return False, "Username or email already exists"
                
                # Create new user
                # Potong password menjadi 72 byte sebelum di-hash
                truncated_password = password[:72]
                password_hash = pwd_context.hash(truncated_password)
                
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                    (username, email, password_hash)
                )
                user_id = cursor.fetchone()[0]
                self.connection.commit()
                return True, user_id
        except Exception as e:
            logger.exception("Failed to create user")
            self.connection.rollback()
            return False, str(e)
    
    def authenticate_user(self, username, password):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT id, username, password_hash FROM users WHERE username = %s OR email = %s",
                    (username, username)
                )
                user = cursor.fetchone()
                
                if not user or not pwd_context.verify(password, user['password_hash']):
                    return None
                
                # Update last login
                cursor.execute(
                    "UPDATE users SET last_login = %s WHERE id = %s",
                    (datetime.now(), user['id'])
                )
                self.connection.commit()
                
                return dict(user)
        except Exception as e:
            logger.exception("Failed to authenticate user")
            return None

    # --- FUNGSI SESSION BARU ---
    def create_session(self, user_id, remember_me=False):
        """Create a new session for the user."""
        try:
            with self.connection.cursor() as cursor:
                # Generate a secure token
                token = secrets.token_urlsafe(32)
                
                # Set expiration time
                if remember_me:
                    expires_at = datetime.now() + timedelta(days=30)  # 30 days for "remember me"
                else:
                    expires_at = datetime.now() + timedelta(hours=2)   # 2 hours for normal session
                
                cursor.execute(
                    "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s) RETURNING token",
                    (token, user_id, expires_at)
                )
                self.connection.commit()
                return token
        except Exception as e:
            logger.exception("Failed to create session")
            self.connection.rollback()
            return None

    def validate_session(self, token):
        """Validate a session token and return user data if valid."""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # --- PERUBAAN DI SINI ---
                # Pilih u.id agar konsisten dengan fungsi authenticate_user
                cursor.execute("""
                    SELECT u.id, u.username, u.email 
                    FROM sessions s
                    JOIN users u ON s.user_id = u.id
                    WHERE s.token = %s AND s.expires_at > %s
                """, (token, datetime.now()))
                
                result = cursor.fetchone()
                if result:
                    return dict(result)
                return None
        except Exception as e:
            logger.exception("Failed to validate session")
            return None

    def delete_session(self, token):
        """Delete a session (for logout)."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("DELETE FROM sessions WHERE token = %s", (token,))
                self.connection.commit()
                return True
        except Exception as e:
            logger.exception("Failed to delete session")
            self.connection.rollback()
            return False

    def cleanup_expired_sessions(self):
        """Remove expired sessions from the database."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("DELETE FROM sessions WHERE expires_at <= %s", (datetime.now(),))
                deleted_count = cursor.rowcount
                self.connection.commit()
                logger.info(f"Cleaned up {deleted_count} expired sessions.")
                return deleted_count
        except Exception as e:
            logger.exception("Failed to cleanup expired sessions")
            return 0
    
    # --- PERBARUI FUNGSI SPREADSHEET ---
    def add_spreadsheet(self, user_id, spreadsheet_id, spreadsheet_name):
        """Add a spreadsheet with a user-defined name."""
        try:
            with self.connection.cursor() as cursor:
                # Jika spreadsheet sudah ada, update nama yang diberikan user
                cursor.execute(
                    """
                    INSERT INTO user_spreadsheets (user_id, spreadsheet_id, spreadsheet_name) 
                    VALUES (%s, %s, %s) 
                    ON CONFLICT (user_id, spreadsheet_id) 
                    DO UPDATE SET spreadsheet_name = EXCLUDED.spreadsheet_name
                    """,
                    (user_id, spreadsheet_id, spreadsheet_name)
                )
                self.connection.commit()
                return True
        except Exception as e:
            logger.exception("Failed to add spreadsheet")
            self.connection.rollback()
            return False

    def delete_spreadsheet(self, user_id, spreadsheet_id):
        """Remove a spreadsheet from a user's account."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_spreadsheets WHERE user_id = %s AND spreadsheet_id = %s",
                    (user_id, spreadsheet_id)
                )
                self.connection.commit()
                return cursor.rowcount > 0  # Return True if a row was deleted
        except Exception as e:
            logger.exception("Failed to delete spreadsheet")
            self.connection.rollback()
            return False

    def get_user_spreadsheets(self, user_id):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM user_spreadsheets WHERE user_id = %s ORDER BY created_at DESC",
                    (user_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.exception("Failed to get user spreadsheets")
            return []