import pandas as pd
from database import clear_certificates, add_certificate


def load_certificates_from_excel(excel_path: str) -> int:
    """
    Load certificates from BIM Excel file.
    Expected format: Column 0 = certificate number, Column 1 = expiry date
    Returns count of loaded certificates.
    """
    try:
        df = pd.read_excel(excel_path, header=None)
        
        # Clear existing certificates
        clear_certificates()
        
        count = 0
        for _, row in df.iterrows():
            cert_number = str(row[0]).strip() if pd.notna(row[0]) else ""
            
            # Handle date
            if pd.notna(row[1]):
                if isinstance(row[1], str):
                    expiry_date = row[1]
                else:
                    try:
                        expiry_date = row[1].strftime('%Y-%m-%d')
                    except:
                        expiry_date = str(row[1])
            else:
                expiry_date = ""
            
            if cert_number:
                if add_certificate(cert_number, expiry_date):
                    count += 1
        
        return count
    except Exception as e:
        raise Exception(f"Грешка при зареждане на сертификати: {str(e)}")


def load_certificates_safe(excel_path: str) -> str:
    """
    Safe wrapper for loading certificates with error handling.
    Returns status message.
    """
    try:
        count = load_certificates_from_excel(excel_path)
        return f"Успешно заредени {count} сертификата"
    except Exception as e:
        return f"Грешка: {str(e)}"
