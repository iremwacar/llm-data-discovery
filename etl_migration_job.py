import psycopg2

# --- KONFİGÜRASYON ---
DB_CONFIG = {
    "host": "localhost",
    "port": 5435,
    "database": "llm_discovery_demo",
    "user": "postgres",
    "password": "Yenisifre12345"
}

def run_relational_migration():
    print("🚀 İlişkisel (ID Bazlı) Golden Record ETL Görevi Başlıyor...\n")
    
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    print("[1/3] Ana tablo (pii_master_vault) sıfırdan oluşturuluyor...")
    cursor.execute("""
        DROP TABLE IF EXISTS pii_master_vault;
        CREATE TABLE pii_master_vault (
            id SERIAL PRIMARY KEY,
            source_info VARCHAR(255),
            email_address TEXT, phone_number TEXT, ssn TEXT,
            credit_card_number TEXT, national_id_number TEXT, full_name TEXT,
            first_name TEXT, last_name TEXT, tckn TEXT,
            home_address TEXT, date_of_birth TEXT, ip_address TEXT
        );
    """)
    conn.commit()

    print("[2/3] Müşteri verileri ID'leri (customer_id) üzerinden kusursuzca birleştiriliyor...")
    # DÜZELTME: c.id yerine c.customer_id kullanıldı
    customer_query = """
        INSERT INTO pii_master_vault (
            source_info, first_name, last_name, full_name, email_address, 
            phone_number, date_of_birth, national_id_number, home_address, credit_card_number
        )
        SELECT 
            'customers_joined',
            c.first_name, 
            c.last_name, 
            CONCAT(c.first_name, ' ', c.last_name),
            c.email, 
            c.phone_number, 
            CAST(c.date_of_birth AS TEXT), 
            c.national_id,
            CONCAT(a.street_address, ' ', a.district, ' ', a.city),
            p.card_number_masked
        FROM customers c
        LEFT JOIN customer_addresses a ON c.customer_id = a.customer_id
        LEFT JOIN payment_methods p ON c.customer_id = p.customer_id;
    """
    cursor.execute(customer_query)

    print("[3/3] Eksik veriler (Çalışanlar ve Sistem Logları) tabloya ekleniyor...")
    employee_query = """
        INSERT INTO pii_master_vault (
            source_info, first_name, last_name, full_name, email_address, 
            phone_number, ssn
        )
        SELECT 
            'employees',
            first_name, 
            last_name, 
            CONCAT(first_name, ' ', last_name),
            email, 
            phone, 
            social_security_number
        FROM employees;
    """
    cursor.execute(employee_query)

    audit_query = """
        INSERT INTO pii_master_vault (source_info, ip_address)
        SELECT 'audit_logs', ip_address FROM audit_logs WHERE ip_address IS NOT NULL;
    """
    cursor.execute(audit_query)

    conn.commit()
    cursor.close()
    conn.close()
    print("\n[BİTTİ] Veriler ID'ler üzerinden bağlandı. Ahmet Yılmaz tek satırda birleşti ve SSN/IP verileri başarıyla çekildi!")

if __name__ == "__main__":
    run_relational_migration()