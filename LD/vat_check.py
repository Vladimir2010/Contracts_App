import requests
import xml.etree.ElementTree as ET
import re
import datetime

def format_to_title_case(text):
    """
    Converts ALL CAPS text to Title Case.
    Keeps legal forms and abbreviations in upper case.
    """
    if not text:
        return ""
    # If text is not primarily uppercase, leave it as is
    if any(c.islower() for c in text):
        return text
    
    words = text.split()
    formatted_words = []
    
    # List of terms that should stay uppercase
    uppers = ["ЕООД", "ООД", "АД", "ЕТ", "ЕИК", "ДДС", "ЗДДС", "Д", "И"]
    
    for word in words:
        clean_word = re.sub(r'[^A-ZА-Я]', '', word.upper())
        if clean_word in uppers:
            formatted_words.append(word.upper())
        else:
            # Handle hyphenated names like "Влахова-Иванова"
            parts = word.split('-')
            formatted_parts = [p.capitalize() for p in parts]
            formatted_words.append("-".join(formatted_parts))
            
    return " ".join(formatted_words)

def format_company_name(name):
    """
    Formats company name: "Name" EOOD/OOD or ET "Name".
    """
    if not name:
        return ""
    
    # Normalize and Title Case
    name = format_to_title_case(name)
    
    # Patterns for legal forms
    forms = [r"ЕООД", r"ООД", r"АД"]
    found_form = None
    
    # 1. Handle ET
    if re.search(r'\bЕТ\b', name, re.IGNORECASE):
        # Remove ET and any hyphens/spaces around it
        name = re.sub(r'\bЕТ\b', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*-\s*', ' ', name)
        name = " ".join(name.split())
        return f'ЕТ "{name}"'
    
    # 2. Handle others (EOOD, OOD, AD)
    for form in forms:
        if re.search(rf'\b{form}\b', name, re.IGNORECASE):
            found_form = form
            # Remove the form and hyphens
            name = re.sub(rf'\s*-\s*\b{form}\b', '', name, flags=re.IGNORECASE)
            name = re.sub(rf'\b{form}\b', '', name, flags=re.IGNORECASE)
            break
            
    # Clean up name from hyphens and extra spaces
    name = re.sub(r'\s*-\s*$', '', name).strip()
    name = " ".join(name.split()).strip(' -')
    
    if found_form:
        return f'"{name}" {found_form}'
    return f'"{name}"'

def parse_bulgarian_address(address_str):
    """
    Extracts City, Postal Code, and District from a Bulgarian address string.
    """
    city = ""
    post_code = ""
    district = ""
    
    if not address_str:
        return city, post_code, district

    # 1. City
    city_match = re.search(r'(?:гр\.|с\.|град|село)\.?\s*([A-ZА-Яa-zа-я\d\-]{2,}(?:\s+[A-ZА-Яa-zа-я\d\-]+)*)', address_str, re.IGNORECASE)
    if city_match:
        city = city_match.group(1).strip()
        city = re.split(r'\s+(?:обл\.|р-н|район|municipality|region|municipiality)', city, flags=re.IGNORECASE)[0].strip()
        city = re.split(r'[,;]', city)[0].strip()
        city = re.sub(r'\s+\d{4}$', '', city).strip()

    # 2. Postal Code
    post_match = re.search(r'(?:p\.c\.|пощ\. код|ПК)?\s*(\d{4})\b', address_str)
    if post_match:
        post_code = post_match.group(1)
        
    # 3. District (Район) - Capture multi-word names until comma or other known keyword
    dist_match = re.search(r'(?:р-н|район)\.?\s*([A-ZА-Яa-zа-я\d\-\s]+?)(?=[,;.]|ж\.к\.|кв\.|ул\.|бул\.|№|\d{4}|$)', address_str, re.IGNORECASE)
    if dist_match:
        district = dist_match.group(1).strip()
    
    return city, post_code, district

def ensure_street_prefix(address_segment):
    """
    Ensures 'ул.' prefix for street names if missing.
    """
    if not address_segment:
        return ""
    
    # Common prefixes that signify we don't need to add 'ул.'
    prefixes = [r"ул\.", r"улица", r"бул\.", r"булевард", r"ж\.к\.", r"комплекс", r"кв\.", r"квартал", r"пл\.", r"площад", r"м-т", r"местност"]
    pattern = r'^\s*(?:' + '|'.join(prefixes) + r')\b'
    
    if re.search(pattern, address_segment, re.IGNORECASE):
        return address_segment
        
    # If it looks like a lone street name (starts with letter, followed by number or just a name)
    # Don't add if it's just a number or building info like 'бл.'
    if re.match(r'^[A-ZА-Я]{2,}', address_segment, re.IGNORECASE) and not re.match(r'^(?:бл\.|вх\.|ет\.|ап\.|№)\b', address_segment, re.IGNORECASE):
        return f"ул. {address_segment}"
        
    return address_segment

def clean_full_address(address_str, city_name="", district_name=""):
    """
    Removes City, Region, and Postal Code from address. Ensures District is present.
    Preserves and polishes street names and building info.
    """
    if not address_str:
        return ""
        
    cleaned = address_str
    
    # 0. Specialized removal of junk labels found in non-VAT addresses
    # Handle the "bul./ul." slash specifically
    cleaned = re.sub(r'бул\./ул\.?', 'ул. ', cleaned, flags=re.IGNORECASE)
    
    junk_labels = [
        r'Населено място:', r'\(столица\)', r'Столична', r'я\.ъ', r'п\.к\.?', r'/(?:ул|бул)', r'Държава:', r'Country:', r'Region:', r'Municipality:',
        r'община', r'област', r'БЪЛГАРИЯ', r'BULGARIA'
    ]
    for junk in junk_labels:
        cleaned = re.sub(junk, '', cleaned, flags=re.IGNORECASE)

    # 1. Remove obvious metadata prefixes e.g. "Област: СОФИЯ"
    cleaned = re.sub(r'(?:^|[,;])\s*[A-ZА-Яa-zа-я\s]+:\s*', ', ', cleaned)

    # 2. Remove Region
    cleaned = re.sub(r'обл\.\s*[A-ZА-Яa-zа-я\s\(\)d\-]+(?=[,;.]|\s+гр\.|\s+с\.|\s|$)', '', cleaned, flags=re.IGNORECASE)
    
    # 3. Remove City prefix and name
    cleaned = re.sub(r'(?:гр\.|с\.|град|село)\.?\s*[A-ZА-Яa-zа-я\d\-]+(?=[,;.]|\s|$)', '', cleaned, flags=re.IGNORECASE)
    if city_name:
        def remove_city_smart(m):
            if m.group(1): return m.group(0) 
            return ""
        pattern = rf'((?:ул\.|бул\.|ж\.к\.|пл\.|квартал|кв\.|улица)\s*)?\b{re.escape(city_name)}\b'
        cleaned = re.sub(pattern, remove_city_smart, cleaned, flags=re.IGNORECASE)
        
    # 4. Remove Postal Code
    cleaned = re.sub(r'(?:p\.c\.|пощ\. код|ПК)?\s*\d{4}\b', '', cleaned)
    
    # 5. Handle District
    current_dist = district_name
    if not current_dist:
        # Better district regex that stops at known street prefixes
        d_match = re.search(r'(?:р-н|район)\.?\s*([A-ZА-Яa-zа-я\d\-\s]+?)(?=[,;.]|ж\.к\.|кв\.|ул\.|бул\.|№|No|\d{4}|$)', cleaned, re.IGNORECASE)
        if d_match:
            current_dist = d_match.group(1).strip()
            
    # Remove all district mentions from the main string
    cleaned = re.sub(r'(?:р-н|район)\.?\s*[A-ZА-Яa-zа-я\d\-\s]+?(?=[,;.]|ж\.к\.|кв\.|ул\.|бул\.|№|No|\d{4}|$)', '', cleaned, flags=re.IGNORECASE)

    # 6. Process segments to ensure prefixes
    segments = [s.strip() for s in re.split(r'[,;]', cleaned) if s.strip()]
    processed_segments = []
    for seg in segments:
        ps = ensure_street_prefix(seg)
        processed_segments.append(ps)
    
    cleaned = ", ".join(processed_segments)

    # 7. Final cleaning of punctuation and casing
    cleaned = re.sub(r'№', 'No ', cleaned)
    cleaned = re.sub(r'[,;]\s*[,;]', ', ', cleaned) # Collapse multiple punctuations
    cleaned = re.sub(r'\s{2,}', ' ', cleaned) # Collapse double spaces
    cleaned = cleaned.strip(' ,;.')
    
    if not any(c.islower() for c in cleaned):
        cleaned = format_to_title_case(cleaned)

    # 8. Prepend district
    if current_dist:
        dist_str = f"р-н {format_to_title_case(current_dist)}"
        if cleaned:
            return f"{dist_str}, {cleaned}"
        return dist_str
        
    return cleaned

def check_tr(eik: str):
    """
    Fetch company details (Name, MOL, Address) from the Bulgarian Commercial Register API.
    """
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.999Z")
        url = f"https://portal.registryagency.bg/CR/api/Deeds/{eik}?entryDate={ts}&loadFieldsFromAllLegalForms=false"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://portal.registryagency.bg/CR/en/Reports/ActiveConditionTabResult"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
            
        data = response.json()
        mol = ""
        tr_address = ""
        tr_latin_name = ""
        
        # Extract Legal Form and Company Name more reliably
        company_name = data.get("companyName", "")
        legal_form_data = data.get("legalForm")
        legal_form = ""
        if isinstance(legal_form_data, dict):
            legal_form = legal_form_data.get("name", "")
            
        if legal_form and legal_form not in company_name:
            company_name = f"{company_name} {legal_form}"
        
        # Traverse rows to find specific fields if companyName is not enough or to get MOL/Address
        for section in data.get("sections", []):
            for sub_deed in section.get("subDeeds", []):
                for group in sub_deed.get("groups", []):
                    for field in group.get("fields", []):
                        code = field.get("nameCode")
                        html = field.get("htmlData", "")
                        clean_text = re.sub(r'<[^>]+>', ' ', html).strip()
                        clean_text = " ".join(clean_text.split())
                        
                        if code == "CR_F_7_L": # Managers
                            if not mol: mol = clean_text
                            elif clean_text not in mol: mol += f"; {clean_text}"
                        elif code == "CR_F_5_L": # Address
                            tr_address = clean_text
                        elif code == "CR_F_2_L": # Company Name / Full Name
                            # Priorities: use the one with legal form, or the longest one
                            up = clean_text.upper()
                            has_form = any(f in up for f in ["ООД", "ЕООД", "ЕТ", "АД"])
                            if not company_name or (has_form and not any(f in company_name.upper() for f in ["ООД", "ЕООД"])):
                                company_name = clean_text
                            elif len(clean_text) > len(company_name) and not any(f in company_name.upper() for f in ["ООД", "ЕООД"]):
                                company_name = clean_text
                        elif code == "CR_F_3_L": # Full legal form description
                            # Map "Еднолично дружество с ограничена отговорност" -> ЕООД etc.
                            lf_map = {
                                "ЕДНОЛИЧНО ДРУЖЕСТВО С ОГРАНИЧЕНА ОТГОВОРНОСТ": "ЕООД",
                                "ДРУЖЕСТВО С ОГРАНИЧЕНА ОТГОВОРНОСТ": "ООД",
                                "АКЦИОНЕРНО ДРУЖЕСТВО": "АД",
                                "ЕДНОЛИЧЕН ТЪРГОВЕЦ": "ЕТ"
                            }
                            up_lf = clean_text.upper()
                            for long_f, short_f in lf_map.items():
                                if long_f in up_lf:
                                    legal_form = short_f
                                    break
                        elif code == "CR_F_4_L": # Legal Form (abbreviation or Latin)
                            if not legal_form: 
                                # Only take it if it looks like an abbreviation
                                if clean_text.upper() in ["ЕООД", "ООД", "ЕТ", "АД"]:
                                    legal_form = clean_text.upper()
                            if not tr_latin_name and re.match(r'^[A-Z\s]+$', clean_text):
                                tr_latin_name = clean_text
                            
        # If legal form is separate, append it
        if legal_form and legal_form.upper() not in company_name.upper():
            company_name = f"{company_name} {legal_form}"
            
        # Clean MOL
        if mol:
            mol = re.sub(r',?\s*(?:Country|Държава):.*$', '', mol, flags=re.IGNORECASE).strip()

        return {"name": company_name, "mol": mol, "tr_address": tr_address}
    except Exception as e:
        print(f"TR Check Exception: {e}")
        return None

def check_vat(eik: str):
    """
    Check VAT registration using EU VIES SOAP API and enrich with TR data.
    Returns: Dict with valid, name, address, mol, city, postal_code or None
    """
    # 0. Clean EIK
    eik = re.sub(r'\D', '', str(eik))
    if not eik: return None
    
    # 1. Base structure
    result_data = {"valid": False, "name": "", "address": "", "mol": "", "city": "", "postal_code": ""}
    
    country_code = "BG"
    url = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
    headers = {"Content-Type": "text/xml; charset=utf-8"}

    soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
        <soapenv:Body>
            <tns:checkVat>
                <tns:countryCode>{country_code}</tns:countryCode>
                <tns:vatNumber>{eik}</tns:vatNumber>
            </tns:checkVat>
        </soapenv:Body>
    </soapenv:Envelope>"""

    try:
        v_resp = requests.post(url, data=soap_body, headers=headers, timeout=10)
        if v_resp.status_code == 200:
            root = ET.fromstring(v_resp.text)
            ns = {"ns": "urn:ec.europa.eu:taxud:vies:services:checkVat:types"}
            
            valid = root.find(".//ns:valid", ns)
            name = root.find(".//ns:name", ns)
            addr = root.find(".//ns:address", ns)

            if valid is not None and valid.text == "true":
                result_data["valid"] = True
                result_data["name"] = name.text if name is not None else ""
                result_data["address"] = (addr.text or "").replace("\n", " ").strip()
    except Exception as e:
        print(f"VIES Exception: {e}")

    # 2. TR Enrichment (Crucial for name and MOL if VIES is missing/invalid)
    tr_data = check_tr(eik)
    tr_dist = ""
    if tr_data:
        # If VIES didn't find the name, use the one from TR
        if not result_data["name"]:
            result_data["name"] = tr_data.get("name", "")
            
        result_data["mol"] = format_to_title_case(tr_data.get("mol", ""))
        tr_addr = tr_data.get("tr_address", "")
        
        # Extract metadata from TR address
        _, _, tr_dist = parse_bulgarian_address(tr_addr)
        
        # Use TR address if VIES is empty
        if not result_data["address"]:
            result_data["address"] = tr_addr
    
    # 3. Parse City, Postal Code, and District
    city, post, dist = parse_bulgarian_address(result_data["address"])
    if not dist:
        dist = tr_dist # Fallback
    
    result_data["city"] = format_to_title_case(city)
    result_data["postal_code"] = post
    
    # 4. Final Formatting
    if result_data["name"]:
        result_data["name"] = format_company_name(result_data["name"])
        
    result_data["address"] = clean_full_address(result_data["address"], result_data["city"], dist)

    return result_data
