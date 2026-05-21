#!/usr/bin/env python3
"""Gera SECRET_KEY e FERNET_KEY para produção."""

import secrets
from cryptography.fernet import Fernet

print("SECRET_KEY=" + secrets.token_urlsafe(48))
print("FERNET_KEY=" + Fernet.generate_key().decode())
