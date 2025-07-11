# LedgerLift Backend

This is a minimal FastAPI backend for the LedgerLift prototype. It accepts Excel/CSV uploads, parses them, and returns simulated AI mapping and error detection results.

## Requirements
- Python 3.8+
- pip

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the backend server:
   ```bash
   uvicorn backend:app --reload
   ```
   By default, this runs at http://127.0.0.1:8000

## API Usage
- **POST** `/upload`
  - Form-data: `file` (Excel or CSV file)
  - Returns: JSON with mapped entries, errors, and columns

## Frontend Integration
- The backend has CORS enabled for local development.
- Update your frontend JavaScript to POST the uploaded file to `http://127.0.0.1:8000/upload` and display the results in the workflow steps.

---
This is a prototype. For production, add authentication, error handling, and real AI mapping logic. 