import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

def send_email_with_attachment(smtp_config: dict, recipient: str, subject: str, body: str, attachment_path: str = None) -> bool:
    """
    Send an email with an optional attachment using SMTP.
    
    smtp_config example:
    {
        'server': 'smtp.gmail.com',
        'port': 587,
        'user': 'your-email@gmail.com',
        'password': 'your-app-password',
        'use_tls': True
    }
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_config.get('user')
        msg['To'] = recipient
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {os.path.basename(attachment_path)}",
            )
            msg.attach(part)
            
        # Connect and send
        server_host = smtp_config.get('server')
        port = int(smtp_config.get('port', 587))
        
        # Determine connection type
        if port == 465:
            server = smtplib.SMTP_SSL(server_host, port)
        else:
            server = smtplib.SMTP(server_host, port)
            server.ehlo()
            if smtp_config.get('use_tls'):
                server.starttls()
                server.ehlo()
            
        server.login(smtp_config.get('user'), smtp_config.get('password'))
        server.send_message(msg)
        server.quit()
        
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"Error sending email: Authentication failed ({e}). Please use an App Password for Gmail.")
        return False
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
