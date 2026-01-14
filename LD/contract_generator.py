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

def generate_service_contract(client_data: Dict[str, Any], devices: List[Dict[str, Any]], template_path: str, output_dir: str) -> str:
    """
    Generate a service contract from a template.
    Surgical version using exact template strings.
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template НЕ е намерен: {template_path}")

    # Handle legacy .doc format
    is_temp_docx = False
    temp_docx_path = None
    if template_path.lower().endswith('.doc') and not template_path.lower().endswith('.docx'):
        try:
            temp_docx_path = doc_to_docx(template_path)
            template_path = temp_docx_path
            is_temp_docx = True
        except Exception as e:
            raise Exception(f"Грешка при работа с .doc файла. Детайли: {str(e)}")

    doc = Document(template_path)
    
    # Data Preparation
    c_num = clean_xml_string(client_data.get('contract_number', ''))
    c_name = clean_xml_string(client_data.get('company_name', ''))
    mol = clean_xml_string(client_data.get('mol', ''))
    eik_pure = clean_numeric(client_data.get('eik', ''))
    
    is_vat = str(client_data.get('vat_registered', '')).lower() == 'да'
    vat_prefix = "BG" if is_vat else ""
    eik_with_vat = f"{vat_prefix}{eik_pure}"
    
    now = datetime.now()
    date_str = now.strftime('%d.%m.%Y')
    date_long = format_date_long_bg(now)

    # 1. SPECIAL CASE: The header on Page 1 (P2)
    # Paragraph: № (номер на догово ДНЕШНА ДАТА)/кт: (ИМЕ къ към Договор...
    for para in doc.paragraphs:
        p_text = para.text
        if "номер на догово" in p_text and "ДНЕШНА ДАТА" in p_text:
            # We search for the specific parenthesis string
            # It might looks like (номер на догово ДНЕШНА ДАТА)
            combined_ph = "(номер на догово ДНЕШНА ДАТА)"
            if combined_ph in p_text:
                replace_text_all(doc, combined_ph, f"{c_num} {date_str}")
            else:
                # Fallback: just replace substrings
                replace_text_all(doc, "номер на догово", c_num)
                replace_text_all(doc, "ДНЕШНА ДАТА", date_str)

        if "(ИМЕ къ" in p_text:
             replace_text_all(doc, "(ИМЕ къ", f"({c_name}")
        if "(ИМЕ)" in p_text:
             replace_text_all(doc, "(ИМЕ)", c_name)

    # 2. SPECIAL CASE: EIK / BULSTAT (P4)
    # Placeholder: (РЕГИСТРАЦИЯ ПО ЗДДС АКО ИМА СЕ ПИШЕ BG ИЛИ НИЩО и ЕИК)
    vat_ph = "(РЕГИСТРАЦИЯ ПО ЗДДС АКО ИМА СЕ ПИШЕ BG ИЛИ НИЩО и ЕИК)"
    replace_text_all(doc, vat_ph, eik_with_vat)

    # 3. GLOBAL ROBUST MAPPINGS
    global_mappings = [
        ("(номер на договор)", c_num),
        ("(НОМЕР НА ДОГОВОР)", c_num),
        ("(номер на дог)", c_num),
        ("(ДОГ НОМ)", c_num),
        ("(ДОГ НОМЕР)", c_num),
        ("(ДОГ. НОМ)", c_num),
        ("(ДОГ.НОМ)", c_num),
        ("(ДАТА)", date_str),
        ("(ДНЕШНА ДАТА)", date_str),
        ("(ДАТА НА ИЗДАВАНЕ)", date_str),
        ("(дата)", date_str),
        ("(ДАТА: НЕДЕЛЯ,11.ЯНУАРИ.2026 г.)", date_long),
        ("(ИМЕ НА ФИРМА)", c_name),
        ("(ИМЕ НА ФИРМАТА)", c_name),
        ("(име на фирма във формат: „името“ ЕООД/ООД/)", c_name),
        ("„името“ ЕООД/ООД/", c_name),
        ("(АКО ИМА ЗДДС СЕ ПИШЕ BG ИНАЧЕ НИЩО)", vat_prefix),
        ("(ЕИК)", eik_with_vat),
        ("(БУЛСТАТ)", eik_with_vat),
        ("(МОЛ)", mol),
        ("(мол)", mol),
        ("(ТЕЛЕФОН)", clean_xml_string(client_data.get('phone1', ''))),
        ("(АДРЕС НА ФИРМАТА)", clean_xml_string(client_data.get('address', ''))),
        ("Приложение № 1/(дата)/", f"Приложение № 1/{date_str}/"),
        ("Приложение № 2 /(ДАТА)/", f"Приложение № 2 /{date_str}/"),
        ("(ДАТА НА ИЗТИЧАНЕ)", date_str), # Placeholder for expiry
    ]
    
    for ph, val in global_mappings:
        replace_text_all(doc, ph, val)

    # 4. Device Slots (Annex 1)
    for i in range(5):
        if i < len(devices):
            dev = devices[i]
            obj_name = clean_xml_string(dev.get('object_name', ''))
            obj_addr = clean_xml_string(dev.get('object_address', ''))
            obj_phone = clean_xml_string(dev.get('object_phone', ''))
            model = clean_xml_string(dev.get('model', ''))
            sn = clean_numeric(dev.get('serial_number', ''))
            fm = clean_numeric(dev.get('fiscal_memory', ''))
            
            replace_text_once(doc, "(ИМЕ НА ОБЕКТ)", obj_name)
            replace_text_once(doc, "(АДРЕС НА ОБЕКТ)", obj_addr)
            replace_text_once(doc, "(ТЕЛЕФОН)", obj_phone)
            replace_text_once(doc, "(МОЛ)", mol)
            replace_text_once(doc, f"{i+1}.(МОДЕЛ)", model)
            replace_text_once(doc, "(МОДЕЛ)", model)
            replace_text_once(doc, "(СЕРИЕН НОМ)", sn)
            replace_text_once(doc, "(ФП НОМЕР)", fm)
        else:
            # Clear slot
            slots = ["(ИМЕ НА ОБЕКТ)", "(АДРЕС НА ОБЕКТ)", "(ТЕЛЕФОН)", "(МОЛ)", 
                     f"{i+1}.(МОДЕЛ)", "(МОДЕЛ)", "(СЕРИЕН НОМ)", "(ФП НОМЕР)"]
            for ph in slots:
                replace_text_once(doc, ph, "")

    # 5. Handle Expiry Date in Annex 2
    if devices:
        expiry = str(devices[0].get('contract_expiry', ''))
        if expiry:
            try:
                dt_exp = datetime.strptime(expiry, '%Y-%m-%d')
                exp_str = dt_exp.strftime('%d.%m.%Y')
                replace_text_all(doc, "(ДАТА НА ИЗТИЧАНЕ)", exp_str)
                replace_text_all(doc, "(дата на изтичане на договора)", exp_str)
            except: pass

    # 6. ULTRASAFE CLEANUP
    # We ONLY remove things that are in ALL-CAPS or match known placeholder keywords.
    # We DO NOT touch lowercase words like (дванадесет) or phrases in parentheses.
    # We also avoid deleting (дванадесет) specifically.
    
    def safe_re_cleanup(text):
        # Find all content in parentheses
        matches = re.finditer(r"\((.*?)\)", text)
        result = text
        for match in matches:
            content = match.group(1)
            # If content is EMPTY, we leave it? No, if it was () we probably replaced it.
            # If content contains lowercase letters (except for specific short words like 'кт'), we assume it's legitimate text.
            # (дванадесет) has only lowercase.
            if any(c.islower() for c in content) and len(content) > 3:
                continue
            
            # If it's all caps or contains keywords, it's a placeholder
            keywords = ["ДОГ", "ДАТА", "НОМ", "ИМЕ", "ЕИК", "БУЛСТАТ", "МОЛ", "ТЕЛЕФОН", "ОБЕКТ", "АДРЕС", "МОДЕЛ", "ФП"]
            if any(kw in content.upper() for kw in keywords) or content.isupper():
                result = result.replace(match.group(0), "")
        return result

    for para in doc.paragraphs:
        if "(" in para.text and ")" in para.text:
            fixed = safe_re_cleanup(para.text)
            if fixed != para.text:
                para.text = fixed
                
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    fixed = safe_re_cleanup(para.text)
                    if fixed != para.text:
                        para.text = fixed

    # Save and Cleanup
    safe_company = "".join([c for c in c_name if c.isalnum() or c in (' ', '-', '_')]).strip()
    output_filename = f"{c_num} {safe_company}.docx"
    output_path = os.path.join(output_dir, output_filename)
    
    doc.save(output_path)
    if is_temp_docx and temp_docx_path and os.path.exists(temp_docx_path):
        try: os.remove(temp_docx_path)
        except: pass
    return output_path
