import requests
import xml.etree.ElementTree as ET
from tkinter import *
from tkinter import Menu

def check_vat():
    eik = entry.get()
    country_code = "BG"  # Код за България
    url = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
    headers = {"Content-Type": "text/xml; charset=utf-8"}

    # SOAP заявка към VIES API
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
        response = requests.post(url, data=soap_body, headers=headers)

        if response.status_code == 200:
            root_xml = ET.fromstring(response.text)
            valid_element = root_xml.find(".//{urn:ec.europa.eu:taxud:vies:services:checkVat:types}valid")

            if valid_element is not None and valid_element.text == "true":
                result_label.config(text="Фирмата е регистрирана по ЗДДС ✅", fg="green")
            else:
                result_label.config(text="Фирмата НЕ е регистрирана по ЗДДС ❌", fg="red")
        else:
            result_label.config(text="Грешка при свързването с VIES!", fg="orange")
    except Exception as e:
        result_label.config(text=f"Грешка: {e}", fg="red")

# Функция за контекстното меню (десен бутон)
def show_context_menu(event):
    context_menu.post(event.x_root, event.y_root)

# Функции за Cut, Copy, Paste, Select All
def cut():
    entry.event_generate("<<Cut>>")

def copy():
    entry.event_generate("<<Copy>>")

def paste():
    entry.event_generate("<<Paste>>")

def select_all():
    entry.select_range(0, END)
    entry.icursor(END)

# Мапиране на клавишите за поддръжка на българска клавиатура
key_map = {
    "a": "а", "A": "А",
    "c": "с", "C": "С",
    "x": "х", "X": "Х",
    "v": "в", "V": "В",
    "A": "А", "C": "С", "X": "Х", "V": "В"
}

# Функция за клавишни комбинации
def key_shortcuts(event):
    if event.keysym in ["a", "A", "ф", "Ф"] and event.state & 4:  # Ctrl+A (английска и българска клавиатура)
        select_all()
        return "break"
    if event.keysym in ["c", "C", "с", "С"] and event.state & 4:  # Ctrl+C
        copy()
        return "break"
    if event.keysym in ["x", "X", "ч", "Ч"] and event.state & 4:  # Ctrl+X
        cut()
        return "break"
    if event.keysym in ["v", "V", "м", "М"] and event.state & 4:  # Ctrl+V
        paste()
        return "break"

# Функция за натискане на Enter/NumEnter
def check_on_enter(event):
    check_vat()

# Създаване на Tkinter GUI
root = Tk()
root.title("Проверка на ЗДДС регистрация")
root.iconbitmap("vladpos_logo.ico")
root.geometry("400x200")

Label(root, text="Въведете БУЛСТАТ (ЕИК):").pack(pady=5)
entry = Entry(root)
entry.pack(pady=5)

check_button = Button(root, text="Провери", command=check_vat)
check_button.pack(pady=5)

result_label = Label(root, text="", font=("Arial", 12))
result_label.pack(pady=10)

# Създаване на контекстно меню (десен бутон)
context_menu = Menu(root, tearoff=0)
context_menu.add_command(label="Cut", command=cut)
context_menu.add_command(label="Copy", command=copy)
context_menu.add_command(label="Paste", command=paste)
context_menu.add_separator()
context_menu.add_command(label="Select All", command=select_all)

# Свързване на контекстното меню към Entry полето
entry.bind("<Button-3>", show_context_menu)  # Десен бутон
entry.bind("<Control-KeyPress>", key_shortcuts)  # Поддържа Ctrl+C, Ctrl+X, Ctrl+V, Ctrl+A
entry.bind("<Return>", check_on_enter)  # Enter проверява
entry.bind("<KP_Enter>", check_on_enter)  # NumPad Enter също проверява

root.mainloop()
