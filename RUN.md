## Running Orbital Log

### 1. Set up Python
1. Install Python 3.10+ and create a venv:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

### 2. Configure the database
1. Start Postgres locally or via Docker:
   ```powershell
   docker compose up -d db
   ```
2. Copy `.env.example` to `.env` and update `DATABASE_URL` if your DB credentials differ.

### 3. Run the API
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The OpenAPI UI is at `http://localhost:8000/docs`.

### 4. Dockerized option
To run both the API and Postgres in containers:
```powershell
docker compose up --build
```
The API listens on port 8000.

### 5. Benchmark (optional)
With the API running:
```powershell
python -m scripts.benchmark --url http://localhost:8000 --workspace 1234567890123456 --requests 500 --concurrency 50
```
For an in-process benchmark using SQLite:
```powershell
python -m scripts.benchmark --inprocess --requests 500 --concurrency 50
```
