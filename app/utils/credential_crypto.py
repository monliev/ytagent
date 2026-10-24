import os
import base64
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
from app.core.config import settings

from typing import Optional

def derive_channel_key(channel_id: Optional[int] = None) -> Fernet:
    """Derive a channel-specific (or global if channel_id is None/0) encryption key from master key using HKDF.
    
    Args:
        channel_id: Database channel ID, or None/0 for global credentials.
        
    Returns:
        Fernet: A Fernet symmetric cipher initialized with the derived key.
    """
    cid = channel_id if channel_id is not None else 0
    master_key = base64.urlsafe_b64decode(settings.TOKEN_ENCRYPTION_KEY)
    salt = f"channel:{cid}".encode("utf-8")
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"ytagent-oauth-token",
    )
    
    derived_key = base64.urlsafe_b64encode(hkdf.derive(master_key))
    return Fernet(derived_key)

def encrypt_token(channel_id: Optional[int], plaintext: str) -> str:
    """Encrypt a plaintext string for a specific channel or global scope.
    
    Args:
        channel_id: Database channel ID or None/0 for global credentials.
        plaintext: The credentials or token content to encrypt.
        
    Returns:
        str: Encrypted token base64 string.
    """
    f = derive_channel_key(channel_id)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def decrypt_token(channel_id: Optional[int], ciphertext: str) -> str:
    """Decrypt an encrypted cipher string for a specific channel or global scope with fallback.
    
    Args:
        channel_id: Database channel ID or None/0 for global credentials.
        ciphertext: The encrypted ciphertext base64 string.
        
    Returns:
        str: Decrypted plaintext string.
    """
    try:
        f = derive_channel_key(channel_id)
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except Exception:
        # Fallback to global key (cid=0) if channel_id decryption fails
        if channel_id:
            f_global = derive_channel_key(0)
            return f_global.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        raise
