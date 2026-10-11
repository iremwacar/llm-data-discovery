from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from sqlalchemy import create_engine, MetaData, inspect, text, Column, String, Integer, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from cryptography.fernet import Fernet
import os
import uuid
import json
import requests
import re
import numpy as np
from datetime import datetime
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="LLM-Based Database Data Discovery System")
security = HTTPBasic()

# ==========================================
# GÜVENLİK: ŞİFRELEME (ENCRYPTION) ALTYAPISI
# ==========================================
# Uygulama her başladığında aynı anahtarı kullanması için bir dosya oluşturuyoruz
KEY_FILE = "secret.key"
if not os.path.exists(KEY_FILE):
    with open(KEY_FILE, "wb") as f:
        f.write(Fernet.generate_key())

with open(KEY_FILE, "rb") as f:
    FERNET_KEY = f.read()

cipher_suite = Fernet(FERNET_KEY)

def encrypt_data(data: str) -> str:
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    return cipher_suite.decrypt(encrypted_data.encode()).decode()

# ==========================================
# SİSTEM VERİTABANI (SQLITE) ALTYAPISI
# ==========================================
Base = declarative_base()
sys_engine = create_engine("sqlite:///system_metadata.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sys_engine)

class MetadataRecord(Base):
    __tablename__ = "metadata_records"
    metadata_id = Column(String, primary_key=True)
    db_name = Column(String)
    host = Column(String)
    port = Column(Integer)
    username = Column(String)
    encrypted_password = Column(String)  # Şifreler artık açık tutulmayacak
    creation_date = Column(String)

class ColumnRecord(Base):
    __tablename__ = "column_records"
    column_id = Column(String, primary_key=True)
    metadata_id = Column(String, ForeignKey("metadata_records.metadata_id", ondelete="CASCADE"))
    table_name = Column(String)
    column_name = Column(String)
    data_type = Column(String)

# Tabloları oluştur
Base.metadata.create_all(bind=sys_engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 12 KATEGORİ İÇİN ZENGİNLEŞTİRİLMİŞ SEMANTİK PROTOTİPLER ---
CATEGORY_PROTOTYPES = {
    "Email Address": "Kişisel ve kurumsal e-posta adresleri. Örnek: ahmet.yilmaz@gmail.com, info@sirketim.com.tr, user@yahoo.com",
    "Phone Number": "Mobil, sabit hat ve uluslararası telefon numaraları. Örnek: +905321234567, 0555 123 45 67, +1-555-123-4567",
    "Social Security Number (SSN)": "Amerikan sosyal güvenlik numarası. Örnek: 123-45-6789, 987-65-4321",
    "National ID Number": "Pasaport numarası veya yabancı kimlik kartları. Örnek: U12345678, A9876543, P-123456",
    "Full Name": "Kişilerin hem adı hem de soyadını içeren tam isimler. Örnek: Ahmet Yılmaz, Ayşe Fatma Kaya, John Doe, Zeynep Çelik",
    "First Name": "Kişilerin SADECE ilk adları (soyisim yok). Örnek: Ahmet, Mehmet, Ayşe, Fatma, John, Sarah",
    "Last Name / Surname": "Kişilerin SADECE soyadları (isim yok). Örnek: Yılmaz, Kaya, Demir, Smith, Johnson",
    "Home Address": "Açık ev veya iş adresleri. Sokak, bina no, kat, mahalle, ilçe, şehir, posta kodu içerir. Örnek: Atatürk Mah. Cumhuriyet Sok. No:5 Daire:12 Kadıköy/İstanbul",
    "Date of Birth": "Kişilerin doğum tarihleri. Örnek: 1990-05-15, 15/05/1990, 22.11.1985",
    "Non_PII": "Kişisel veri OLMAYAN sıradan metinler, şirket adları, ürün açıklamaları, rastgele ID'ler, tarihler veya teknik veriler."
}

prototype_embeddings = {}

def get_openai_embedding(text_input: str, api_key: str) -> list:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"input": text_input, "model": "text-embedding-3-small"}
    response = requests.post("https://api.openai.com/v1/embeddings", headers=headers, json=payload)
    if response.status_code == 200:
        return response.json()["data"][0]["embedding"]
    raise Exception(f"Embedding Hatası: {response.text}")

@app.on_event("startup")
def load_prototypes():
    print("Vektör prototipleri hesaplanıyor (RAG Init)...")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("UYARI: OPENAI_API_KEY bulunamadı!")
        return
    for category, text_desc in CATEGORY_PROTOTYPES.items():
        try:
            prototype_embeddings[category] = get_openai_embedding(text_desc, api_key)
        except:
            pass
    print("Vektör uzayı hazır!")

# --- DETERMINİSTİK KURAL MOTORU ---
def is_tckn(val: str) -> bool:
    val = str(val).strip()
    if not re.match(r'^[1-9]{1}[0-9]{10}$', val): return False
    digits = [int(d) for d in val]
    if (sum(digits[0:9:2]) * 7 - sum(digits[1:8:2])) % 10 != digits[9]: return False
    if sum(digits[0:10]) % 10 != digits[10]: return False
    return True

def is_luhn_credit_card(val: str) -> bool:
    val = str(val).replace(" ", "").replace("-", "")
    if not val.isdigit() or len(val) < 13 or len(val) > 19: return False
    total = sum(int(d) if i % 2 == 0 else (int(d) * 2 - 9 if int(d) * 2 > 9 else int(d) * 2) 
                for i, d in enumerate(val[::-1]))
    return total % 10 == 0

def evaluate_deterministic_rules(samples: list) -> dict:
    counts = {"TCKN (Turkish Citizenship Number)": 0, "Credit Card Number": 0, "Email Address": 0, "IP Address": 0}
    total = len(samples)
    if total == 0: return None
    
    for s in samples:
        s = str(s).strip()
        if is_tckn(s): counts["TCKN (Turkish Citizenship Number)"] += 1
        elif is_luhn_credit_card(s): counts["Credit Card Number"] += 1
        elif re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', s): counts["Email Address"] += 1
        elif re.match(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$', s): counts["IP Address"] += 1
            
    for label, count in counts.items():
        if count >= total / 2 and count > 0:
            prob = round(count / total, 2)
            probs_dict = {
                "Email Address": 0, "Phone Number": 0, "Social Security Number (SSN)": 0,
                "Credit Card Number": 0, "National ID Number": 0, "Full Name": 0,
                "First Name": 0, "Last Name / Surname": 0, "TCKN (Turkish Citizenship Number)": 0,
                "Home Address": 0, "Date of Birth": 0, "IP Address": 0, "Non_PII": 0
            }
            probs_dict[label] = prob
            probs_dict["Non_PII"] = round(1.0 - prob, 2)
            return {"primary_label": label, "confidence_score": prob, "probabilities": probs_dict, "is_sensitive_pii": True}
    return None

def get_openai_chat_completion(prompt: str, api_key: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o-mini", "response_format": { "type": "json_object" }, "temperature": 0.0,
        "messages": [
            {"role": "system", "content": "Sen 12 resmi PII kategorisine göre sınıflandırma yapan bir veri güvenliği asistanısın."},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    if response.status_code == 200: return json.loads(response.json()["choices"][0]["message"]["content"])
    raise Exception(f"Chat API Hatası: {response.text}")


# ==========================================
# 1. AUTHENTICATION SERVICE
# ==========================================
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != os.getenv("API_USER", "admin") or credentials.password != os.getenv("API_PASSWORD", "secret"):
        raise HTTPException(status_code=401, detail="Hatalı giriş", headers={"WWW-Authenticate": "Basic"})
    return credentials.username

@app.get("/auth", summary="1. Authentication Service")
def authenticate(username: str = Depends(verify_credentials)):
    return {"message": "Authenticated successfully", "user": username}


# ==========================================
# 2. DATABASE METADATA EXTRACTION SERVICE
# ==========================================
class DBConnectionInput(BaseModel):
    host: str; port: int; database: str; username: str; password: str

@app.post("/db/metadata", summary="2. Database Metadata Extraction & Storage Service")
def extract_metadata(db_input: DBConnectionInput, db: Session = Depends(get_db), username: str = Depends(verify_credentials)):
    try:
        db_url = f"postgresql://{db_input.username}:{db_input.password}@{db_input.host}:{db_input.port}/{db_input.database}"
        engine = create_engine(db_url)
        metadata = MetaData()
        metadata.reflect(bind=engine)
        
        metadata_id = str(uuid.uuid4())
        
        # Parolayı şifreleyerek kalıcı veritabanına kaydet
        new_meta = MetadataRecord(
            metadata_id=metadata_id, db_name=db_input.database, host=db_input.host, 
            port=db_input.port, username=db_input.username, 
            encrypted_password=encrypt_data(db_input.password),
            creation_date=datetime.utcnow().isoformat() + "Z"
        )
        db.add(new_meta)
        
        tables_info = []
        for table_name, table in metadata.tables.items():
            columns_info = []
            for column in table.columns:
                col_id = str(uuid.uuid4())
                columns_info.append({"column_id": col_id, "column_name": column.name, "data_type": str(column.type)})
                
                # Kolonları kalıcı veritabanına kaydet
                db.add(ColumnRecord(
                    column_id=col_id, metadata_id=metadata_id, 
                    table_name=table_name, column_name=column.name, data_type=str(column.type)
                ))
            tables_info.append({"table_name": table_name, "columns": columns_info})
            
        db.commit()
        return {"metadata_id": metadata_id, "tables": tables_info}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================
# 3. METADATA LIST SERVICE
# ==========================================
@app.get("/metadata", summary="3. Metadata List Service")
def list_metadata(db: Session = Depends(get_db), username: str = Depends(verify_credentials)):
    records = db.query(MetadataRecord).all()
    result = []
    for r in records:
        table_count = db.query(ColumnRecord.table_name).filter(ColumnRecord.metadata_id == r.metadata_id).distinct().count()
        result.append({
            "metadata_id": r.metadata_id, "database_name": r.db_name,
            "creation_date": r.creation_date, "table_count": table_count
        })
    return result


# ==========================================
# 4. METADATA DETAIL SERVICE
# ==========================================
@app.get("/metadata/{metadata_id}", summary="4. Metadata Detail Service")
def get_metadata_detail(metadata_id: str, db: Session = Depends(get_db), username: str = Depends(verify_credentials)):
    meta = db.query(MetadataRecord).filter(MetadataRecord.metadata_id == metadata_id).first()
    if not meta: raise HTTPException(status_code=404, detail="Metadata bulunamadı.")
    
    columns = db.query(ColumnRecord).filter(ColumnRecord.metadata_id == metadata_id).all()
    
    tables_dict = {}
    for c in columns:
        if c.table_name not in tables_dict: tables_dict[c.table_name] = []
        tables_dict[c.table_name].append({"column_id": c.column_id, "column_name": c.column_name, "data_type": c.data_type})
        
    tables_info = [{"table_name": t_name, "columns": cols} for t_name, cols in tables_dict.items()]
    return {"metadata_id": metadata_id, "tables": tables_info}


# ==========================================
# 5. METADATA DELETE SERVICE
# ==========================================
@app.delete("/metadata/{metadata_id}", summary="5. Metadata Delete Service")
def delete_metadata(metadata_id: str, db: Session = Depends(get_db), username: str = Depends(verify_credentials)):
    meta = db.query(MetadataRecord).filter(MetadataRecord.metadata_id == metadata_id).first()
    if not meta: raise HTTPException(status_code=404, detail="Metadata bulunamadı.")
    
    db.query(ColumnRecord).filter(ColumnRecord.metadata_id == metadata_id).delete()
    db.delete(meta)
    db.commit()
    
    return {"deletion_status": "Success", "message": f"Metadata {metadata_id} başarıyla silindi."}


# ==========================================
# 6. DATA CLASSIFICATION SERVICE
# ==========================================
class ClassifyInput(BaseModel):
    column_id: str
    sample_count: int = 10

@app.post("/classify", summary="6. Data Classification Service")
def classify_column(input_data: ClassifyInput, db: Session = Depends(get_db), username: str = Depends(verify_credentials)):
    col_id = input_data.column_id
    limit = input_data.sample_count
    
    col_record = db.query(ColumnRecord).filter(ColumnRecord.column_id == col_id).first()
    if not col_record: raise HTTPException(status_code=404, detail="Geçersiz Column ID.")
    
    meta_record = db.query(MetadataRecord).filter(MetadataRecord.metadata_id == col_record.metadata_id).first()
    
    try:
        # Şifreli parolayı çöz ve veritabanı bağlantısını kur
        decrypted_password = decrypt_data(meta_record.encrypted_password)
        db_url = f"postgresql://{meta_record.username}:{decrypted_password}@{meta_record.host}:{meta_record.port}/{meta_record.db_name}"
        engine = create_engine(db_url)
        
        table_name, column_name = col_record.table_name, col_record.column_name
        
        insp = inspect(engine)
        pk_constraint = insp.get_pk_constraint(table_name)
        pk_col = pk_constraint['constrained_columns'][0] if pk_constraint.get('constrained_columns') else "id"

        query = text(f"SELECT {pk_col}, {column_name} FROM {table_name} WHERE {column_name} IS NOT NULL LIMIT {limit}")
        with engine.connect() as conn:
            result = conn.execute(query).fetchall()
            
        if not result: return {"message": "Veri yok."}

        reference_ids = [row[0] for row in result]
        sampled_values = [str(row[1]) for row in result]
        
        rule_result = evaluate_deterministic_rules(sampled_values)
        if rule_result:
            rule_result["sample_reference_ids"] = reference_ids
            return {"column_id": col_id, "table_name": table_name, "column_name": column_name, "source": "Deterministic_Rule_Engine", "classification": rule_result}
            
        api_key = os.getenv("OPENAI_API_KEY")
        sample_text_combined = " | ".join(sampled_values)
        sample_vector = get_openai_embedding(sample_text_combined, api_key)
        
        vector_hints = {}
        if prototype_embeddings:
            sample_vec_np = np.array(sample_vector).reshape(1, -1)
            for cat, proto_vec in prototype_embeddings.items():
                proto_vec_np = np.array(proto_vec).reshape(1, -1)
                sim = cosine_similarity(sample_vec_np, proto_vec_np)[0][0]
                vector_hints[cat] = round(float(sim), 2)
                
            top_hints = sorted(vector_hints.items(), key=lambda x: x[1], reverse=True)[:3]
            hint_str = ", ".join([f"'{k}' (%{int(v*100)} benzerlik)" for k, v in top_hints])
        else:
            hint_str = "Vektör verisi kullanılamıyor."

        prompt = f"""
        Sen kıdemli bir Veri Yönetişimi Uzmanısın. Aşağıdaki veri örneklerinin 12 resmi PII kategorisi üzerindeki OLASILIK DAĞILIMINI hesapla.
        Sütun Adı: {column_name}
        Veri Örnekleri: {sampled_values}
        🤖 SİSTEM İPUCU (Vektör Uzayı Analizi): Makine öğrenmesi modelimiz bu verinin anlamsal olarak şunlara benzediğini düşünüyor: {hint_str}. 
        ⚠️ KRİTİK GÖREV (LLM TEYİDİ): Sistem ipuçlarını dikkate al ama KÖRLÜĞÜNE KOPYALAMA. Özellikle isim kategorilerinde kendi zekanı kullan:
        1. Örnekler genellikle tekil insan isimleriyse -> First Name
        2. Örnekler Türk/Yabancı soyisimleriyse (çift soyisim olup iki kelime olsalar bile) -> Last Name / Surname
        3. Gerçekten Ad + Soyad formatındaysa -> Full Name
        İZİN VERİLEN KATEGORİLER: Email Address, Phone Number, Social Security Number (SSN), Credit Card Number, National ID Number, Full Name, First Name, Last Name / Surname, TCKN (Turkish Citizenship Number), Home Address, Date of Birth, IP Address, Non_PII.
        SADECE AŞAĞIDAKİ JSON FORMATINDA DÖN (Önce 'reasoning' ile sesli düşün, sonra kararlı skorlar ver. Olasılıklar toplamı 1.0'a olmalı):
        {{
            "reasoning": "Verileri neden bu kategoriye koyduğunu mantıksal olarak açıkla",
            "primary_label": "En yüksek olasılıklı kategori",
            "confidence_score": 0.95,
            "probabilities": {{
                "Email Address": 0.0, "Phone Number": 0.0, "Social Security Number (SSN)": 0.0,
                "Credit Card Number": 0.0, "National ID Number": 0.0, "Full Name": 0.0,
                "First Name": 0.0, "Last Name / Surname": 0.0, "TCKN (Turkish Citizenship Number)": 0.0,
                "Home Address": 0.0, "Date of Birth": 0.0, "IP Address": 0.0, "Non_PII": 0.0
            }},
            "is_sensitive_pii": true
        }}
        """
        
        llm_result = get_openai_chat_completion(prompt, api_key)
        llm_result["sample_reference_ids"] = reference_ids
        
        return {
            "column_id": col_id, "table_name": table_name, "column_name": column_name,
            "vector_space_top_matches": dict(top_hints) if prototype_embeddings else {},
            "source": "LLM_with_Vector_RAG", "classification": llm_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))