from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import List, Tuple
import os


def setup_cyrillic_font():
    """Setup font that supports Cyrillic characters"""
    try:
        # Try to register a font that supports Cyrillic
        # You may need to adjust the font path based on your system
        font_path = "C:\\Windows\\Fonts\\arial.ttf"
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('Arial', font_path))
            return 'Arial'
    except:
        pass
    return 'Helvetica'  # Fallback to default


def export_to_pdf(data: List[Tuple], headers: List[str], filename: str, title: str = "Справка за изтичащи договори") -> bool:
    """
    Export data to PDF document with formatted table.
    
    Args:
        data: List of tuples containing row data
        headers: List of column headers
        filename: Output filename (should end with .pdf)
        title: Document title
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create PDF document
        doc = SimpleDocTemplate(
            filename,
            pagesize=landscape(A4),
            rightMargin=1*cm,
            leftMargin=1*cm,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm
        )
        
        # Setup font
        font_name = setup_cyrillic_font()
        
        # Container for elements
        elements = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=font_name,
            fontSize=16,
            textColor=colors.HexColor('#366092'),
            spaceAfter=20,
            alignment=1  # Center
        )
        
        # Add title
        title_para = Paragraph(title, title_style)
        elements.append(title_para)
        elements.append(Spacer(1, 0.5*cm))
        
        # Prepare table data
        table_data = [headers]
        for row in data:
            table_data.append([str(cell) if cell else "" for cell in row])
        
        # Create table
        table = Table(table_data)
        
        # Table style
        table.setStyle(TableStyle([
            # Header style
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            # Data rows style
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        return True
    
    except Exception as e:
        print(f"Error exporting to PDF: {e}")
        return False
