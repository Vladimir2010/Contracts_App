import pandas as pd
from database import get_connection, add_client, add_device
from typing import Dict, Any


def safe_str(value) -> str:
    """Convert value to string, handling NaN and floats ending in .0"""
    if pd.isna(value):
        return ""
    # Handle floats that are actually integers
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def safe_date(value) -> str:
    """Convert value to date string, handling NaN"""
    if pd.isna(value):
        return ""
    if isinstance(value, str):
        return value
    # If it's a datetime object
    try:
        return value.strftime('%Y-%m-%d')
    except:
        return str(value)


def import_from_excel(excel_path: str) -> tuple[int, int]:
    """
    Import contracts and devices from Excel file.
    Returns (clients_count, devices_count)
    """
    df = pd.read_excel(excel_path, header=None)
    
    clients_added = 0
    devices_added = 0
    
    # Group by contract number to handle multiple devices per contract
    contract_groups = {}
    
    for idx, row in df.iterrows():
        contract_num = safe_str(row[0])  # Column A
        
        if not contract_num:
            continue
        
        # Create client data from row
        client_data = {
            'contract_number': contract_num,
            'status': safe_str(row[1]),  # B
            'contract_start': safe_date(row[2]),  # C
            'contract_expiry': safe_date(row[3]),  # D
            'company_name': safe_str(row[4]),  # E
            'city': safe_str(row[5]),  # F
            'postal_code': safe_str(row[6]),  # G
            'address': safe_str(row[7]),  # H
            'eik': safe_str(row[12]),  # M
            'vat_registered': safe_str(row[13]),  # N
            'mol': safe_str(row[10]),  # K
            'phone1': safe_str(row[16]),  # Q
            'phone2': safe_str(row[17])  # R
        }
        
        # Create device data from row
        device_data = {
            'fdrid': safe_str(row[11]),  # L
            'euro_done': safe_str(row[14]) == 'э',  # O - check for special symbol
            'object_name': safe_str(row[18]),  # S
            'object_address': safe_str(row[19]),  # T
            'object_phone': safe_str(row[20]),  # U
            'model': safe_str(row[21]),  # V
            'certificate_number': safe_str(row[22]),  # W
            'certificate_expiry': safe_date(row[23]),  # X
            'serial_number': safe_str(row[24]),  # Y
            'fiscal_memory': safe_str(row[25])  # Z
        }
        
        # Check if we already have this contract
        if contract_num not in contract_groups:
            # New contract - add client
            client_id = add_client(client_data)
            contract_groups[contract_num] = client_id
            clients_added += 1
        else:
            # Existing contract - use existing client_id
            client_id = contract_groups[contract_num]
        
        # Add device
        add_device(client_id, device_data)
        devices_added += 1
    
    return clients_added, devices_added


def import_contracts_simple(excel_path: str) -> str:
    """
    Simple import function with error handling.
    Returns status message.
    """
    try:
        clients, devices = import_from_excel(excel_path)
        return f"Успешно импортирани:\n{clients} договора\n{devices} устройства"
    except Exception as e:
        return f"Грешка при импорт: {str(e)}"
