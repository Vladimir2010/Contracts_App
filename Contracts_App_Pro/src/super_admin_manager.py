"""
Super Admin Manager - Encrypted storage for super admin credentials
Uses Fernet encryption with machine-specific key
"""
import os
import json
import uuid
import platform
import hashlib
from cryptography.fernet import Fernet
import base64

def _get_encryption_key():
    """Generate encryption key from machine-specific data"""
    # Get machine-specific identifiers
    mac_address = uuid.getnode()  # MAC address as integer
    hostname = platform.node()     # Computer name
    
    # Combine into unique string
    machine_id = f"{mac_address}-{hostname}-VLADPOS-SECRET"
    
    # Hash to get consistent 32-byte key
    hash_obj = hashlib.sha256(machine_id.encode())
    key_bytes = hash_obj.digest()
    
    # Fernet needs base64-encoded 32-byte key
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    
    return fernet_key

def _get_storage_path():
    """Get path to encrypted super admin file"""
    from path_utils import get_app_root
    data_dir = os.path.join(get_app_root(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, ".super_admin.enc")

def save_super_admin(username, password_hash, full_name):
    """
    Save super admin credentials in encrypted format
    
    Args:
        username: Super admin username
        password_hash: Hashed password
        full_name: Full name of super admin
    
    Returns:
        bool: True if saved successfully
    """
    try:
        # Create data dict
        data = {
            "username": username,
            "password_hash": password_hash,
            "full_name": full_name
        }
        
        # Convert to JSON
        json_data = json.dumps(data)
        
        # Encrypt
        key = _get_encryption_key()
        fernet = Fernet(key)
        encrypted_data = fernet.encrypt(json_data.encode())
        
        # Save to file
        storage_path = _get_storage_path()
        with open(storage_path, 'wb') as f:
            f.write(encrypted_data)
        
        return True
    except Exception as e:
        print(f"Error saving super admin: {e}")
        return False

def load_super_admin():
    """
    Load super admin credentials from encrypted storage
    
    Returns:
        dict: Super admin data or None if not found/invalid
    """
    try:
        storage_path = _get_storage_path()
        
        if not os.path.exists(storage_path):
            return None
        
        # Read encrypted file
        with open(storage_path, 'rb') as f:
            encrypted_data = f.read()
        
        # Decrypt
        key = _get_encryption_key()
        fernet = Fernet(key)
        decrypted_data = fernet.decrypt(encrypted_data)
        
        # Parse JSON
        data = json.loads(decrypted_data.decode())
        
        return data
    except Exception as e:
        print(f"Error loading super admin: {e}")
        return None

def super_admin_exists():
    """
    Check if super admin encrypted file exists
    
    Returns:
        bool: True if file exists
    """
    storage_path = _get_storage_path()
    return os.path.exists(storage_path)
