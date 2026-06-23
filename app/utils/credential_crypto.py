import os
import base64
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
from app.core.config import settings

def derive_channel_key(channel_id: int) -> Fernet:
    """Derive a channel-specific encryption key from the master key using HKDF.
    
    Args:
        channel_id: Database channel ID.
        
    Returns:
        Fernet: A Fernet symmetric cipher initialized with the derived key.
    """
    master_key = base64.urlsafe_b64decode(settings.TOKEN_ENCRYPTION_KEY)
    salt = f"channel:{channel_id}".encode("utf-8")
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"ytagent-oauth-token",
    )
    
    derived_key = base64.urlsafe_b64encode(hkdf.derive(master_key))
    return Fernet(derived_key)

def encrypt_token(channel_id: int, plaintext: str) -> str:
    """Encrypt a plaintext string for a specific channel.
    
    Args:
        channel_id: Database channel ID.
        plaintext: The credentials or token content to encrypt.
        
    Returns:
        str: Encrypted token base64 string.
    """
    f = derive_channel_key(channel_id)
    return f.encrypt(plaintext.encode("utf-8")).decode("utf-8")

def decrypt_token(channel_id: int, ciphertext: str) -> str:
    """Decrypt an encrypted cipher string for a specific channel.
    
    Args:
        channel_id: Database channel ID.
        ciphertext: The encrypted ciphertext base64 string.
        
    Returns:
        str: Decrypted plaintext string.
    """
    f = derive_channel_key(channel_id)
    return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
