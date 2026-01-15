import os
from datetime import datetime
from docx import Document
from typing import Dict, Any, List
import locale

# Try to set Bulgarian locale for dates
try:
    locale.setlocale(locale.LC_ALL, 'bg_BG.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'bulgarian')
    except:
        pass

def format_date_long_bg(dt=None):
    """Format date as: понеделник, 12.януари. 2026 г."""
    if dt is None:
        dt = datetime.now()
    
    days = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]
    months = ["януари", "февруари", "март", "април", "май", "юни", 
              "юли", "август", "септември", "октомври", "ноември", "декември"]
    
    day_name = days[dt.weekday()]
    month_name = months[dt.month - 1]
    
    return f"{day_name}, {dt.day}.{month_name}. {dt.year} г."

import re

def clean_xml_string(s):
    """Aggressively remove any character that could break Word's XML 1.0 body"""
    if s is None: return ""
    s = str(s)
    # XML 1.0 valid chars: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    # We use a whitelist approach for maximum safety.
    return "".join(c for c in s if ord(c) in (0x9, 0xA, 0xD) or (0x20 <= ord(c) <= 0xD7FF) or (0xE000 <= ord(c) <= 0xFFFD))

def surgical_replace(para, placeholder, replacement, once=False):
    """
    The most robust way to replace text in python-docx:
    1. If placeholder is in a single run, replace it there.
    2. If split across runs, merge into the first run and clear others.
    Preserves all Run objects to avoid XML handle corruption.
    """
    if placeholder not in para.text:
        return False
        
    replacement = clean_xml_string(replacement)
    
    # Try one-run replacement first
    for run in para.runs:
        if placeholder in run.text:
            run.text = run.text.replace(placeholder, replacement, 1 if once else -1)
            return True
            
    # Handle split runs (the 'Safe Merge' strategy)
    full_text = para.text
    if once:
        new_text = full_text.replace(placeholder, replacement, 1)
    else:
        new_text = full_text.replace(placeholder, replacement)
        
    if new_text != full_text and para.runs:
        # Move all text to run 0, clear others. 
        # This keeps the XML structure identical but changes the content.
        para.runs[0].text = new_text
        for i in range(1, len(para.runs)):
            para.runs[i].text = ""
        return True
        
    return False

def replace_text_once(doc, placeholder, replacement):
    """Surgical replacement of the first occurrence found in the document"""
    for para in doc.paragraphs:
        if surgical_replace(para, placeholder, replacement, once=True):
            return True
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if surgical_replace(para, placeholder, replacement, once=True):
                        return True
    return False

def replace_text_all(doc, placeholder, replacement):
    """Surgical replacement of all occurrences in the document"""
    found = False
    for para in doc.paragraphs:
        if surgical_replace(para, placeholder, replacement, once=False):
            found = True
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if surgical_replace(para, placeholder, replacement, once=False):
                        found = True
    return found

def doc_to_docx(doc_path):
    """Convert .doc to .docx using pywin32 with robust cleanup"""
    import win32com.client
    import pythoncom
    
    # Initialize COM for the thread
    pythoncom.CoInitialize()
    
    word = None
    doc = None
    try:
        # Use DispatchEx to ensure a fresh instance
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0 # wdAlertsNone
        
        doc_path = os.path.abspath(doc_path)
        docx_path = doc_path + "x"
        
        print(f"Конвертиране на: {doc_path}")
        
        # Open the document (ReadOnly to avoid lock issues)
        doc = word.Documents.Open(doc_path, ReadOnly=True, ConfirmConversions=False)
        
        # Save as docx (FileFormat 16)
        doc.SaveAs2(docx_path, FileFormat=16)
        
        doc.Close(False)
        doc = None
        
        return docx_path
    except Exception as e:
        print(f"Грешка при COM конвертиране: {e}")
        raise e
    finally:
        try:
            if doc: doc.Close(False)
        except: pass
        try:
            if word: word.Quit()
        except: pass
        pythoncom.CoUninitialize()

def clean_numeric(val):
    """Remove .0 from numbers like serials or fiscal memory"""
    if val is None: return ""
    s = str(val).strip()
    if s.endswith('.0'):
        return s[:-2]
    return s

def format_phone_custom(phone):
    """Format phone as 0888/728-005 or 02/870-5657"""
    if not phone: return ""
    digits = re.sub(r'\D', '', str(phone))
    if not digits: return str(phone)
    
    # 0888728005 -> 0888/728-005
    if len(digits) == 10 and digits.startswith('08'):
        return f"{digits[:4]}/{digits[4:7]}-{digits[7:]}"
    # 028705657 -> 02/870-5657
    if len(digits) == 9 and digits.startswith('02'):
        return f"{digits[:2]}/{digits[2:5]}-{digits[5:]}"
    # Fallback for other formats
    if len(digits) > 6:
        return f"{digits[:-6]}/{digits[-6:-3]}-{digits[-3:]}"
    return str(phone)

def format_date_bg(dt, fmt_type='A'):
    """
    fmt_type A: 15/01/26 г.
    fmt_type B: 15 януари 2026 г.
    fmt_type C: четвъртък, 15 януари 2026 г.
    fmt_type D: 15.01.2027 г. (for device list)
    """
    if not dt or not isinstance(dt, datetime):
        return ""
    
    days = ["понеделник", "вторник", "сряда", "четвъртък", "петък", "събота", "неделя"]
    months = ["януари", "февруари", "март", "април", "май", "юни", 
              "юли", "август", "септември", "октомври", "ноември", "декември"]
    
    if fmt_type == 'A':
        return dt.strftime('%d/%m/%y г.')
    elif fmt_type == 'B':
        return f"{dt.day} {months[dt.month - 1]} {dt.year} г."
    elif fmt_type == 'C':
        return f"{days[dt.weekday()]}, {dt.day} {months[dt.month - 1]} {dt.year} г."
    elif fmt_type == 'D':
        return dt.strftime('%d.%m.%Y г.')
    return dt.strftime('%d.%m.%Y')

def generate_service_contract(client_data: Dict[str, Any], devices: List[Dict[str, Any]], template_path: str, output_dir: str) -> str:
    """
    Generate service contract using strict {1}-{51} placeholder mapping.
    """
    if not os.path.exists(template_path):
        # Check root directory as fallback
        root_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), template_path)
        if os.path.exists(root_path):
            template_path = root_path
        else:
            raise FileNotFoundError(f"Template НЕ е намерен: {template_path}")

    doc = Document(template_path)
    
    now = datetime.now()
    # Contract start date as datetime object for comparison
    start_date_str = client_data.get('contract_start', '')
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    except:
        start_date = now

    # Basic data
    c_num = str(client_data.get('contract_number', ''))
    c_name = str(client_data.get('company_name', ''))
    c_addr = str(client_data.get('address', ''))
    mol = str(client_data.get('mol', ''))
    eik_pure = clean_numeric(client_data.get('eik', ''))
    is_vat = str(client_data.get('vat_registered', '')).lower() == 'да'
    eik_val = f"BG{eik_pure}" if is_vat else eik_pure
    
    mappings = {
        "{1}": c_num,
        "{2}": format_date_bg(now, 'A'),
        "{3}": c_name,
        "{4}": c_addr,
        "{5}": eik_val,
        "{6}": format_phone_custom(client_data.get('phone1', '')),
        "{7}": mol,
        "{8}": format_date_bg(now, 'B'),
        "{9}": c_num,
        "{10}": format_date_bg(now, 'A'),
        "{46}": format_date_bg(now, 'B'),
        "{47}": c_num,
        "{48}": format_date_bg(now, 'A'),
        "{49}": format_date_bg(now, 'C'),
        "{50}": "Г" if start_date.date() == now.date() else "А"
    }

    # Device Mapping (11-45, grouped by 7 fields per device)
    for i in range(5):
        base_idx = 11 + (i * 7)
        if i < len(devices):
            dev = devices[i]
            mappings[f"{{{base_idx}}}"] = str(dev.get('object_name', ''))
            mappings[f"{{{base_idx+1}}}"] = str(dev.get('object_address', ''))
            mappings[f"{{{base_idx+2}}}"] = format_phone_custom(dev.get('object_phone', ''))
            mappings[f"{{{base_idx+3}}}"] = mol
            mappings[f"{{{base_idx+4}}}"] = str(dev.get('model', ''))
            mappings[f"{{{base_idx+5}}}"] = clean_numeric(dev.get('serial_number', ''))
            mappings[f"{{{base_idx+6}}}"] = clean_numeric(dev.get('fiscal_memory', ''))
        else:
            for j in range(7):
                mappings[f"{{{base_idx+j}}}"] = ""

    # {51} - Device list with expiry dates
    device_list_entries = []
    for i, dev in enumerate(devices):
        expiry_str = str(dev.get('contract_expiry', ''))
        expiry_formatted = ""
        try:
            exp_date = datetime.strptime(expiry_str, '%Y-%m-%d')
            expiry_formatted = format_date_bg(exp_date, 'D')
        except:
            expiry_formatted = expiry_str
        
        device_list_entries.append(f"ЕКА No {i+1} до {expiry_formatted}")
    
    mappings["{51}"] = ", ".join(device_list_entries)

    # Perform replacements
    for ph, val in mappings.items():
        replace_text_all(doc, ph, clean_xml_string(val))

    # Save
    safe_company = "".join([c for c in c_name if c.isalnum() or c in (' ', '-', '_')]).strip()
    output_filename = f"{c_num} {safe_company}.docx"
    output_path = os.path.join(output_dir, output_filename)
    
    doc.save(output_path)
    return output_path
