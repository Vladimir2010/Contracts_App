import os
import sys
# Add src to path
sys.path.append(os.path.join(os.getcwd(), "Contracts_App_Pro", "src"))

from contract_generator import generate_repair_protocol

client_data = {
    'company_name': 'Тест Фирма ЕООД',
    'address': 'гр. София, бул. България 1',
    'mol': 'Иван Иванов',
    'phone1': '0888/111-222'
}

device_data = {
    'model': 'Tremol S25',
    'serial_number': 'ZK123456',
    'object_address': 'гр. София, ул. Тестова 5'
}

repair_info = {
    'protocol_id': 1,
    'repair_date': '2026-01-20',
    'problem_description': 'Принтерът не печата - заседнала хартия.'
}

output_dir = os.path.join(os.getcwd(), "test_output")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

template_path = "RepairProtocol_Template.docx"

try:
    print("Генериране на тестов протокол...")
    # Mock get_resource_path if needed, but contract_generator.py handles it
    # We need to make sure resources exist in the right place relative to execution
    path = generate_repair_protocol(client_data, device_data, repair_info, template_path, output_dir)
    print(f"Успех! Файлът е записан в: {path}")
except Exception as e:
    print(f"Грешка: {e}")
    import traceback
    traceback.print_exc()
