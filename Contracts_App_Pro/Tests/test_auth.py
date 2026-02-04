import unittest
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import auth

class TestAuth(unittest.TestCase):
    def test_password_hashing(self):
        password = "SecretPassword123!"
        hashed = auth.hash_password(password)
        
        # Verify it's not the same as plain text
        self.assertNotEqual(password, hashed)
        
        # Verify correct password
        self.assertTrue(auth.verify_password(hashed, password))
        
        # Verify incorrect password
        self.assertFalse(auth.verify_password(hashed, "WrongPassword"))

    def test_hash_different_for_same_password(self):
        # Salts should make hashes different even for same password
        p = "pass"
        h1 = auth.hash_password(p)
        h2 = auth.hash_password(p)
        self.assertNotEqual(h1, h2)

if __name__ == '__main__':
    unittest.main()
