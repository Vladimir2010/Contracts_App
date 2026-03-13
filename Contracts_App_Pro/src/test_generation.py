from contract_generator import generate_service_contract, generate_registration_certificate, generate_deregistration_protocol
import os

def test_contract():
    client_data = {
        'contract_number': '1234',
        'contract_start': '2026-01-01',
        'company_name': 'Тест Фирма ЕООД',
        'address': 'гр. София',
        'eik': '123456789',
        'vat_registered': 'Да',
        'phone1': '0888123456',
        'mol': 'Иван Иванов'
    }
    
    devices = [
        {
            'object_name': 'Магазин',
            'object_address': 'ул. Тест 1',
            'object_phone': '0888654321',
            'model': 'Perfect S',
            'serial_number': 'DY123456',
            'fiscal_memory': '02123456',
            'contract_expiry': '2027-01-01'
        }
    ]
    
    # We need to point to the actual templates. They are in resources/
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    res_dir = os.path.join(os.path.dirname(curr_dir), 'resources')
    out_dir = curr_dir
    
    # We will test DeregProtocol template because it's guaranteed to be there
    # Let's test deregistration protocol
    proto_data = {
        'serial_number': 'DY123456',
        'company_name': 'Тест Фирма ЕООД',
        'address': 'гр. София',
        'eik': '123456789',
        'mol': 'Иван Иванов',
        'object_name': 'Обект 1',
        'object_address': 'ул. Тест',
        'model': 'Perfect S',
        'bim_number': 'BIM000',
        'certificate_expiry': '2030-01-01',
        'fiscal_memory': '020000',
        'fdrid': '5000000',
        'reason': 'Брак',
        'manufacturer': 'Дейзи',
        'turnover': 1500.50
    }
    
    try:
        out_path = generate_deregistration_protocol(
            proto_data, 
            'DeregProtocol_DT123456.docx', 
            out_dir
        )
        print(f"Успешно генериран: {out_path}")
    except Exception as e:
        print(f"Грешка: {e}")

if __name__ == '__main__':
    test_contract()
