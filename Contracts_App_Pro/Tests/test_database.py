import unittest
import sqlite3
import os
import sys
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Use a shared in-memory database for testing so it persists across connections
        # but stays in memory. We need URI mode for this.
        self.db_uri = "file:testdb?mode=memory&cache=shared"
        self.con = sqlite3.connect(self.db_uri, uri=True)
        self.con.row_factory = sqlite3.Row
        
        # Patch DB_PATH and get_connection in database module
        self.path_patcher = patch('database.DB_PATH', self.db_uri)
        # We don't necessarily need to patch get_connection if we patch DB_PATH 
        # but database.py might use sqlite3.connect(DB_PATH) directly or via get_connection
        # The get_connection in database.py uses sqlite3.connect(DB_PATH)
        
        # We need to make sure get_connection also uses URI=True if we use a URI
        self.conn_patcher = patch('database.get_connection', side_effect=lambda: sqlite3.connect(self.db_uri, uri=True))
        
        self.path_patcher.start()
        self.conn_patcher.start()
        
        # Initialize DB structure
        database.init_db()

    def tearDown(self):
        # Close our "keep-alive" connection which will wipe the in-memory DB
        self.con.close()
        self.path_patcher.stop()
        self.conn_patcher.stop()

    def test_init_db(self):
        # init_db is called in setUp, so we just check if tables exist
        cur = self.con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        self.assertIn('clients', tables)
        self.assertIn('devices', tables)
        self.assertIn('users', tables)
        self.assertIn('products', tables)

    def test_add_get_client(self):
        client_data = {
            'contract_number': '123',
            'company_name': 'Test Co',
            'eik': '123456789'
        }
        client_id = database.add_client(client_data)
        self.assertNotEqual(client_id, -1)
        
        client = database.get_client_by_contract('123')
        self.assertIsNotNone(client)
        self.assertEqual(client['company_name'], 'Test Co')

    def test_add_device(self):
        client_id = database.add_client({'contract_number': '123', 'company_name': 'Test Co'})
        device_data = {
            'model': 'Model X',
            'serial_number': 'SN123',
            'euro_done': True
        }
        device_id = database.add_device(client_id, device_data)
        self.assertIsNotNone(device_id)
        
        devices = database.get_devices_by_contract('123')
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]['model'], 'Model X')
        self.assertTrue(devices[0]['euro_done'])

    def test_product_operations(self):
        product_data = {
            'name': 'Propane',
            'category': 'Gas',
            'price': 10.50
        }
        product_id = database.add_product(product_data)
        self.assertIsNotNone(product_id)
        
        products = database.get_all_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]['name'], 'Propane')
        
        # Search
        found = database.search_products('Prop')
        self.assertEqual(len(found), 1)

    def test_user_operations(self):
        # Default admin is created in init_db
        user = database.get_user_by_username('vladpos')
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'admin')
        
        # Add new user
        database.add_user('testuser', 'hash', 'Test User', 'user')
        new_user = database.get_user_by_username('testuser')
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user['full_name'], 'Test User')

if __name__ == '__main__':
    unittest.main()
