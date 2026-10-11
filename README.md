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