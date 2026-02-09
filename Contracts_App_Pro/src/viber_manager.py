import requests
import json

def send_viber_message(token, receiver_id, text):
    """
    Sends a message via Viber Bot API.
    :param token: Viber Bot API Token
    :param receiver_id: Viber User ID (obtain from webhook or manual entry)
    :param text: Message text
    :return: (bool, message/error)
    """
    if not token or not receiver_id:
        return False, "Липсва токен или ID на получател"

    url = "https://chatapi.viber.com/pa/send_message"
    headers = {
        "X-Viber-Auth-Token": token,
        "Content-Type": "application/json"
    }
    
    payload = {
        "receiver": receiver_id,
        "min_api_version": 1,
        "sender": {
            "name": "Contracts App Bot"
        },
        "tracking_data": "tracking data",
        "type": "text",
        "text": text
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        result = response.json()
        
        if result.get("status") == 0:
            return True, "Съобщението е изпратено успешно"
        else:
            return False, f"Грешка от Viber API: {result.get('status_message')}"
    except Exception as e:
        return False, f"Комуникационна грешка: {str(e)}"

def validate_viber_token(token):
    """Simple check if we can reach Viber API with this token"""
    url = "https://chatapi.viber.com/pa/get_account_info"
    headers = {"X-Viber-Auth-Token": token}
    try:
        res = requests.post(url, headers=headers, json={}, timeout=5)
        return res.status_code == 200
    except:
        return False
