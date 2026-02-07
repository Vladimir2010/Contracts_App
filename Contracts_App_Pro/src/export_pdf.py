from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import List, Tuple
import os
from date_utils import format_date_bg

FIXED_EXCHANGE_RATE = 1.95583


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


def generate_invoice_pdf(invoice_data: dict, filename: str) -> bool:
    """
    Generate a professional invoice PDF.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        
        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=15*mm
        )
        
        font_name = setup_cyrillic_font()
        styles = getSampleStyleSheet()
        
        # Custom Styles
        style_header = ParagraphStyle('Header', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=12)
        style_title = ParagraphStyle('Title', parent=styles['Normal'], fontName=font_name, fontSize=18, leading=22, alignment=1, spaceAfter=8)
        style_num = ParagraphStyle('DocNum', parent=styles['Normal'], fontName=font_name, fontSize=12, alignment=1, spaceAfter=15)
        
        elements = []
        
        # 1. Top Section: Supplier vs Buyer
        seller = invoice_data.get('seller', {})
        supplier_info = [
            [Paragraph("<b>ДОСТАВЧИК:</b>", style_header), Paragraph("<b>ПОЛУЧАТЕЛ:</b>", style_header)],
            [Paragraph(seller.get('name', 'Д и Д Фискал Системс ЕООД'), style_header), Paragraph(invoice_data['client_name'], style_header)],
            [Paragraph(f"ЕИК: {seller.get('eik', '205634567')}", style_header), Paragraph(f"ЕИК: {invoice_data['client_eik']}", style_header)],
            [Paragraph(f"ЗДДС: {seller.get('vat', 'BG205634567')}", style_header), Paragraph(f"ЗДДС: {invoice_data['client_vat'] or '--'}", style_header)],
            [Paragraph(f"Адрес: гр. {seller.get('city', 'София')}, {seller.get('address', 'бул. България №1')}", style_header), Paragraph(f"Адрес: {invoice_data['client_address']}", style_header)],
            [Paragraph(f"МОЛ: {seller.get('mol', 'Александър Петров')}", style_header), Paragraph(f"МОЛ: {invoice_data['client_mol'] or '--'}", style_header)],
        ]
        
        top_table = Table(supplier_info, colWidths=[90*mm, 90*mm])
        top_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elements.append(top_table)
        elements.append(Spacer(1, 10*mm))
        
        # 2. Document Title & Number
        doc_type = "ФАКТУРА" if invoice_data['type'] == 'INV' else "ПРОФОРМА ФАКТУРА"
        elements.append(Paragraph(f"<b>{doc_type}</b>", style_title))
        elements.append(Paragraph(f"№ {invoice_data['number']}", style_num))
        
        # Date & Method
        dates_info = [
            [Paragraph(f"Дата на издаване: {format_date_bg(invoice_data['date_issued'])}", style_header), 
             Paragraph(f"Място: София", style_header)],
            [Paragraph(f"Дата на падеж: {format_date_bg(invoice_data['date_due'])}", style_header), 
             Paragraph(f"Плащане: {invoice_data['payment_method']}", style_header)]
        ]
        date_table = Table(dates_info, colWidths=[90*mm, 90*mm])
        elements.append(date_table)
        elements.append(Spacer(1, 10*mm))
        
        # 3. Items Table
        items_headers = ["№", "Описание на стоката / услугата", "Кол.", "Цена", "Стойност"]
        items_data = [items_headers]
        
        for i, item in enumerate(invoice_data.get('items', []), 1):
            items_data.append([
                str(i),
                item['description'],
                f"{item['quantity']:.2f}",
                f"{item['unit_price']:.2f}",
                f"{(item['quantity'] * item['unit_price']):.2f}"
            ])
            
        col_widths = [10*mm, 85*mm, 20*mm, 30*mm, 35*mm]
        items_table = Table(items_data, colWidths=col_widths)
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,-1), font_name),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 5*mm))
        
        # 4. Totals
        subtotal = float(invoice_data.get('total_base', 0))
        vat_rate = float(invoice_data.get('vat_rate', 20))
        vat_amount = float(invoice_data.get('total_vat', 0))
        total = float(invoice_data.get('total_amount', 0))
        
        # If totals not provided, calculate from items
        if subtotal == 0 and invoice_data.get('items'):
            subtotal = sum(i['quantity'] * i['unit_price'] for i in invoice_data['items'])
            vat_amount = subtotal * (vat_rate / 100)
            total = subtotal + vat_amount

        totals_data = [
            ["", "", "Данъчна основа:", f"{subtotal:.2f} {invoice_data.get('currency', 'EUR')}"],
            ["", "", f"ДДС ({vat_rate}%):", f"{vat_amount:.2f} {invoice_data.get('currency', 'EUR')}"],
            ["", "", "ОБЩО ЗА ПЛАЩАНЕ:", Paragraph(f"<b>{total:.2f} {invoice_data.get('currency', 'EUR')}</b>", style_header)]
        ]
        
        # Add BGN equivalent if primary currency is EUR
        if invoice_data.get('currency') == 'EUR':
            total_bgn = total * FIXED_EXCHANGE_RATE
            totals_data.append(["", "", "Равностойност в лева:", f"{total_bgn:.2f} лв."])
        
        totals_table = Table(totals_data, colWidths=[10*mm, 85*mm, 50*mm, 35*mm])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,-1), font_name),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(totals_table)
        
        # 5. Bottom Section
        elements.append(Spacer(1, 15*mm))
        footer_text = f"Забележка: {invoice_data.get('notes', '')}"
        elements.append(Paragraph(footer_text, style_header))
        
        elements.append(Spacer(1, 20*mm))
        sign_info = [
            [Paragraph("Съставил: ..........................", style_header), 
             Paragraph("Получил: ..........................", style_header)]
        ]
        sign_table = Table(sign_info, colWidths=[90*mm, 90*mm])
        elements.append(sign_table)
        
        # Build
        doc.build(elements)
        return True
    except Exception as e:
        print(f"Error generating invoice PDF: {e}")
        return False
