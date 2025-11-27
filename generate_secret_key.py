"""
Generate a Django secret key for use in .env file.

This script generates a secure random secret key compatible with Django.
It uses Python's built-in secrets module, so no Django installation is required.

Usage:
    python generate_secret_key.py
"""

import secrets
import string

def generate_secret_key():
    """
    Generate a Django-compatible secret key.
    Uses the same character set as Django's get_random_secret_key().
    """
    chars = string.ascii_letters + string.digits + '!@#$%^&*(-_=+)'
    return ''.join(secrets.choice(chars) for _ in range(50))

if __name__ == "__main__":
    secret_key = generate_secret_key()
    print("\n" + "=" * 60)
    print("Django Secret Key Generated:")
    print("=" * 60)
    print(secret_key)
    print("=" * 60)
    print("\nAdd this to your .env file as:")
    print(f"DJANGO_SECRET_KEY={secret_key}")
    print("\n")

