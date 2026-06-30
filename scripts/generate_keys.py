"""
Generate secure keys for .env file.
Run: python scripts/generate_keys.py
"""

import secrets
from cryptography.fernet import Fernet

print("# Paste these into your .env file\n")
print(f"APP_SECRET_KEY={secrets.token_urlsafe(64)}")
print(f"APP_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
print(f"JWT_SECRET_KEY={secrets.token_urlsafe(64)}")
