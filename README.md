# LLM-Based Database Data Discovery System 🚀

This project is an AI-powered data discovery and classification system built with **FastAPI**. It scans target PostgreSQL databases, securely stores metadata, and uses a hybrid approach (Deterministic Rule Engine + Vector Similarity (RAG) + LLM Chain of Thought) to accurately classify database columns into 12 predefined PII (Personally Identifiable Information) categories.

## 🌟 Key Features
- **Hybrid Classification Engine:** Uses mathematically deterministic rules (for TCKN/Credit Cards) first, falls back to OpenAI Embeddings (Cosine Similarity), and finalizes with GPT-4o-mini reasoning to prevent hallucination.
- **Secure Storage (Encryption):** Uses `cryptography` (Fernet) to encrypt all database passwords before saving them to the system metadata.
- **Persistent Metadata Vault:** Stores scanned database schemas locally using an in-app `SQLite` database (`system_metadata.db`), avoiding volatile RAM storage.
- **Golden Record ETL (Bonus):** Includes a standalone `etl_migration_job.py` script that uses the API to map and migrate scattered legacy data into a perfectly consolidated, ID-based "Master Vault" table.

## 🛠️ Technology Stack
- **Backend:** Python 3.10, FastAPI, SQLAlchemy
- **AI & LLM:** OpenAI API (`gpt-4o-mini`, `text-embedding-3-small`), Scikit-Learn
- **Security:** Fernet Symmetric Encryption, Basic Authentication
- **Database:** SQLite (System Metadata), PostgreSQL (Target Database)
- **Containerization:** Docker & Docker Compose

## 🚀 Setup & Installation Instructions

### 1. Environment Configuration
Create a `.env` file in the root directory and configure your credentials. You can use the provided `.env.example` as a template:
```bash
cp .env.example .env
```

### 2. Build and Run with Docker
The system is fully containerized. To start the application, simply run:
```bash
docker-compose up --build
```
* **The API will be available at:** `http://localhost:8000`
* **Interactive API Documentation (Swagger UI):** `http://localhost:8000/docs`

## 📡 API Endpoints (Core Services)
- **GET /auth:** Basic authentication test endpoint.
- **POST /db/metadata:** Connects to the target PostgreSQL DB, extracts table/column metadata, assigns unique UUIDs, encrypts the password, and saves the schema to SQLite.
- **GET /metadata:** Lists all scanned metadata records.
- **GET /metadata/{metadata_id}:** Retrieves specific schema details (tables and columns) for a given metadata ID.
- **DELETE /metadata/{metadata_id}:** Deletes the stored metadata and its column registry.
- **POST /classify:** Takes a `column_id`, dynamically fetches sample data from the target DB, and returns a probability distribution across 12 PII categories using the hybrid AI engine.

## 🏗️ Bonus: ETL Migration Job
To test the semantic schema mapping capabilities, run the standalone Python script:
```bash
python etl_migration_job.py
```
This script reads the target database, utilizes SQL JOINs based on `customer_id`, and consolidates all scattered PII data into a unified, clean `pii_master_vault` table.

### 📋 Task 2: Java Migration Methodology & AI Prompt Log

The full Python FastAPI system was ported to Java 21 / Spring Boot 3 using an iterative AI-guided migration strategy[cite: 10].

#### Step 1: Framework & Dependency Setup
* **User Prompt:**
  > "Sen kıdemli bir yazılım mühendisisin. Python ve Java dillerini çok iyi biliyor ve donuştürmeler yapabiliyorsun. FastAPI ile yazılmış bir PII veri keşfi ve sınıflandırma projesini Java Spring Boot 3 ve Java 21 mimarisine taşıyacağız. Proje için gerekli Maven `pom.xml` bağımlılıklarını (Spring Web, Spring Data JPA, Spring Security, Lombok, SQLite JDBC, Jackson, SpringDoc OpenAPI) oluşturabilmem için beni yönlendir."
* **AI Action & Output:** Generated the complete `pom.xml` configuration including `springdoc-openapi-starter-webmvc-ui` for Swagger UI access.

#### Step 2: Security & Encryption Layer Implementation
* **User Prompt:**
  > "FastAPI'deki Basic Auth güvenlik mekanizmasını Spring Security ile kurgula. Ayrıca hedef veritabanı şifrelerini veritabanında güvenle saklamak için AES algoritması kullanan bir `EncryptionService` yaz."
* **AI Action & Output:** Implemented `SecurityConfig.java` enforcing Basic Authentication (`admin`/`secret`) and created `EncryptionService.java` for AES secret key encryption.

#### Step 3: Metadata Extraction Service (`POST /db/metadata`)
* **User Prompt:**
  > "PostgreSQL veritabanı bağlantı bilgilerini alıp, JDBC `DatabaseMetaData` kullanarak veritabanındaki tüm tablo ve kolon bilgilerini çıkartan, kolonlara benzersiz UUID'ler atayan ve SQLite'a kaydeden `MetadataService` ve `MetadataController` sınıflarını yaz."
* **AI Action & Output:** Built dynamic JDBC metadata extraction logic that saves database schema topologies into JPA entities[cite: 11].

#### Step 4: Swagger UI Integration for API Testing
* **User Prompt:**
  > "Python'daki FastAPI `/docs` ekranı gibi tarayıcıdan kolayca test yapabilmemiz için Spring Boot projesine Swagger UI entegrasyonunu nasıl yaparız? Gerekli anotasyonları ve konfigürasyonu sağla."
* **AI Action & Output:** Integrated SpringDoc OpenAPI UI, exposing the interactive documentation interface at `http://localhost:8080/swagger-ui/index.html`.

#### Step 5: Initial LLM Classification Integration (`POST /classify`)
* **User Prompt:**
  > "Hedef veritabanından örnek veriler çekip OpenAI API (`gpt-4o-mini`) modeline gönderen ve 12 PII kategorisinde (EMAIL, PHONE, TCKN, SSN, NAME, ADDRESS vb.) sınıflandırma yapan `ClassificationService` ve `ClassificationController` sınıflarını yaz."
* **AI Action & Output:** Developed `ClassificationService.java` with dynamic SQL sampling query execution (`LIMIT N`) and OpenAI HTTP REST call structure.

#### Step 6: Formatting LLM Response Output (Jackson Integration)
* **User Prompt:**
  > "OpenAI API'den gelen `llm_analysis` yanıtı tek bir string metin olarak kaçış karakterleriyle (`\n`, `\"`) dönüyor. Bunu tarayıcıda temiz ve hiyerarşik bir JSON nesnesi olarak görebilmemiz için Jackson parser kullanarak düzelt."
* **AI Action & Output:** Modified `ClassificationService` using Jackson `ObjectMapper.readValue(content, Object.class)` to parse raw JSON strings directly into clean, nested Java JSON objects.
