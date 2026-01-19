"""
Utility functions for date formatting in Bulgarian format
"""
from datetime import datetime
from PyQt6.QtCore import QDate


def format_date_bg(date_str: str) -> str:
    """
    Convert date string to Bulgarian format: DD.MM.YYYY г.
    
    Args:
        date_str: Date in format YYYY-MM-DD or datetime object
    
    Returns:
        Date in format DD.MM.YYYY г.
    """
    if not date_str:
        return ""
    
    try:
        if isinstance(date_str, str):
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            date_obj = date_str
        
        return date_obj.strftime('%d.%m.%Y') + ' г.'
    except:
        return str(date_str)


def parse_date_bg(date_str: str) -> str:
    """
    Parse Bulgarian format date to YYYY-MM-DD for database
    
    Args:
        date_str: Date in format DD.MM.YYYY г. or DD.MM.YYYY
    
    Returns:
        Date in format YYYY-MM-DD
    """
    if not date_str:
        return ""
    
    try:
        # Remove ' г.' if present
        clean_date = date_str.replace(' г.', '').strip()
        
        # Try to parse DD.MM.YYYY
        date_obj = datetime.strptime(clean_date, '%d.%m.%Y')
        return date_obj.strftime('%Y-%m-%d')
    except:
        return date_str


def qdate_to_bg(qdate: QDate) -> str:
    """
    Convert QDate to Bulgarian format string
    
    Args:
        qdate: QDate object
    
    Returns:
        Date in format DD.MM.YYYY г.
    """
    return qdate.toString('dd.MM.yyyy') + ' г.'


def qdate_to_db(qdate: QDate) -> str:
    """
    Convert QDate to database format
    
    Args:
        qdate: QDate object
    
    Returns:
        Date in format YYYY-MM-DD
    """
    return qdate.toString('yyyy-MM-dd')


def db_to_qdate(date_str: str) -> QDate:
    """
    Convert database date string to QDate
    
    Args:
        date_str: Date in format YYYY-MM-DD
    
    Returns:
        QDate object
    """
    if not date_str:
        return QDate.currentDate()
    
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return QDate(date_obj.year, date_obj.month, date_obj.day)
    except:
        return QDate.currentDate()
