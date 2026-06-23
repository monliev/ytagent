import os
import hmac
import hashlib
import json
import base64
import time
from typing import Optional, Any
from app.core.config import settings

def urlsafe_b64encode(data: bytes) -> str:
    """Encode bytes to URL-safe Base64 string without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def urlsafe_b64decode(data: str) -> bytes:
    """Decode URL-safe Base64 string back to bytes adding necessary padding."""
    rem = len(data) % 4
    if rem > 0:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def create_access_token(subject: Any, expires_in_seconds: int = 86400) -> str:
    """Generate a JWT token using HS256 algorithm with standard python library."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(subject),
        "exp": int(time.time()) + expires_in_seconds
    }
    
    header_b64 = urlsafe_b64encode(json.dumps(header).encode("utf-8"))
    payload_b64 = urlsafe_b64encode(json.dumps(payload).encode("utf-8"))
    
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"), 
        signing_input, 
        hashlib.sha256
    ).digest()
    
    signature_b64 = urlsafe_b64encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """Decode a JWT access token and verify its signature and expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode("utf-8"), 
            signing_input, 
            hashlib.sha256
        ).digest()
        
        expected_sig_b64 = urlsafe_b64encode(expected_sig)
        
        # Prevent timing attack
        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            return None
            
        payload = json.loads(urlsafe_b64decode(payload_b64).decode("utf-8"))
        
        # Verify expiration
        if payload.get("exp", 0) < time.time():
            return None
            
        return payload
    except Exception:
        return None

def hash_password(password: str) -> str:
    """Hash password using PBKDF2 HMAC SHA-256 (Django compatible)."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100000  # 100k iterations
    )
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    key_b64 = base64.b64encode(key).decode("utf-8")
    return f"pbkdf2_sha256$100000${salt_b64}${key_b64}"

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a PBKDF2 HMAC SHA-256 hash."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
            
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("utf-8"))
        stored_key = base64.b64decode(parts[3].encode("utf-8"))
        
        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations
        )
        return hmac.compare_digest(stored_key, computed_key)
    except Exception:
        return False
