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

This message means your app **successfully installed all dependencies and started to deploy**, but then crashed because it’s missing a required package:  
**`python-multipart`**

### Why?
- FastAPI needs `python-multipart` to handle file uploads and form data (like your `/upload` endpoint).
- If it’s not in your `requirements.txt`, deployment will fail with this error.

---

## How to Fix

1. **Add `python-multipart` to your `requirements.txt`** (both in the root and in `LedgerLift/requirements.txt` for consistency):

```
fastapi
uvicorn
pandas
openpyxl
python-multipart
```

2. **Commit and push the change:**
```sh
git add requirements.txt LedgerLift/requirements.txt
git commit -m "Add python-multipart to requirements for file upload support"
git push
```

3. **Re-deploy on Render.**
   - Render will automatically rebuild and your app should work!

---

**Summary:**  
Your app is almost ready! Just add `python-multipart` to your requirements, push, and redeploy.  
Let me know if you want me to make this change for you! 