from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, HTMLResponse, JSONResponse
import pandas as pd
import numpy as np
import io
import logging
import math
import json
import os
import smtplib
from email.message import EmailMessage
import time
from fastapi.responses import StreamingResponse, FileResponse
import io, zipfile
from fastapi.staticfiles import StaticFiles
import sys
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

# Global variable to store the last processed DataFrame
last_processed_df = None
last_processed_sheets = None  # Store all sheets as a dict

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

app = FastAPI()

static_dir = os.path.join(os.path.dirname(__file__), '.')
if not ("pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ):
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

# Explicitly allow your frontend origin (do NOT use "*" with allow_credentials=True)
origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "null"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # <-- explicit origin, not "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net https://www.googletagmanager.com https://www.google-analytics.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net https://www.googletagmanager.com https://www.google-analytics.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "connect-src *;"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'geolocation=()'
        return response
app.add_middleware(SecurityHeadersMiddleware)

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        print(f"Request: {request.method} {request.url.path}")
        response = await call_next(request)
        return response
app.add_middleware(RequestLoggerMiddleware)

USE_VITE_DEV_SERVER = os.environ.get('USE_VITE_DEV_SERVER', '0') == '1'
if not USE_VITE_DEV_SERVER:
    vite_dist = os.path.join(os.path.dirname(__file__), 'dist')
    if os.path.isdir(vite_dist):
        app.mount("/", StaticFiles(directory=vite_dist, html=True), name="static")

def clean_nans(obj):
    import numpy as np
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (np.floating, np.integer)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, dict):
        return {k: clean_nans(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_nans(x) for x in obj]
    else:
        return obj

# Add helper functions near the top

def check_double_entry(df):
    errors = []
    if 'Debit' in df.columns and 'Credit' in df.columns:
        for idx, row in df.iterrows():
            if pd.isnull(row['Debit']) or pd.isnull(row['Credit']):
                errors.append({"row": idx+1, "issue": "Missing Debit or Credit"})
            elif row['Debit'] != row['Credit']:
                errors.append({"row": idx+1, "issue": "Debits and Credits do not balance"})
    return errors

def check_missing_values(df):
    errors = []
    for col in df.columns:
        missing = df[df[col].isnull()]
        for idx in missing.index:
            errors.append({"row": idx+1, "issue": f"Missing value in {col}"})
            if len(errors) >= 25:  # Reduced limit for performance
                break
    return errors

def check_duplicates(df):
    errors = []
    dups = df[df.duplicated()]
    for idx in dups.index:
        errors.append({"row": idx+1, "issue": "Duplicate row"})
    return errors

def check_invalid_dates(df, date_col='Date'):
    errors = []
    if date_col in df.columns:
        for idx, val in df[date_col].items():
            try:
                pd.to_datetime(val)
            except Exception:
                errors.append({"row": idx+1, "issue": "Invalid date"})
    return errors

def validate_account_codes(df, coa_set, code_col='Account'):
    errors = []
    if code_col in df.columns:
        for idx, val in df[code_col].items():
            if val not in coa_set:
                errors.append({"row": idx+1, "issue": f"Unknown account code: {val}"})
    return errors

# --- Enhanced error detection for AI bookkeeping ---

EXCEL_ERROR_CODES = {'#REF!', '#VALUE!', '#DIV/0!', '#NAME?', '#N/A', '#NUM!', '#NULL!'}
REQUIRED_IS_CATEGORIES = {'Revenue', 'Expenses'}
REQUIRED_BS_CATEGORIES = {'Assets', 'Liabilities', 'Equity'}

# Example COA (could be loaded from file or uploaded)
STANDARD_COA = {'1000', '2000', '3000', '4000', '5000', '6000', '7000', '8000', '9000'}

def check_coa_all(df, code_col='Account', coa_set=STANDARD_COA):
    errors = []
    if code_col in df.columns:
        for idx, val in df[code_col].items():
            if str(val) not in coa_set:
                errors.append({"row": idx+1, "issue": f"Unknown account code: {val}"})
    return errors

def check_trial_balance_balance(df):
    errors = []
    if 'Debit' in df.columns and 'Credit' in df.columns:
        total_debit = pd.to_numeric(df['Debit'], errors='coerce').sum()
        total_credit = pd.to_numeric(df['Credit'], errors='coerce').sum()
        if abs(total_debit - total_credit) > 1e-2:
            errors.append({"row": None, "issue": f"Trial balance out of balance: Debits={total_debit}, Credits={total_credit}"})
    return errors

def check_required_categories(df, required, col='Category'):
    errors = []
    if col in df.columns:
        present = set(str(x).strip() for x in df[col].dropna())
        for req in required:
            if req not in present:
                errors.append({"row": None, "issue": f"Missing required category: {req}"})
    return errors

def check_excel_errors(df):
    errors = []
    for col in df.columns:
        if df[col].dtype == object:
            for idx, val in df[col].items():
                if isinstance(val, str) and val.strip().upper() in EXCEL_ERROR_CODES:
                    errors.append({"row": idx+1, "issue": f"Excel error code in {col}: {val}"})
                    if len(errors) >= 25:  # Reduced limit for performance
                        break
    return errors

AUDIT_LOG_PATH = 'audit.log'

# Helper: log audit events
def log_audit(action, details=None, user=None):
    with open(AUDIT_LOG_PATH, 'a', encoding='utf-8') as f:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{ts}] ACTION: {action}"
        if user:
            line += f" USER: {user}"
        if details:
            line += f" DETAILS: {details}"
        f.write(line + '\n')

# --- Input validation for uploads ---
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {'.csv', '.xlsx'}

def allowed_file(filename):
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)

def get_sheet(sheet=None):
    if last_processed_sheets is None:
        return None
    if sheet and sheet in last_processed_sheets:
        return last_processed_sheets[sheet]
    # Default to first sheet
    return next(iter(last_processed_sheets.values()))

@app.get("/")
async def root():
    with open(os.path.join(static_dir, "index.html"), encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    global last_processed_sheets
    # Log file info
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("upload")
    logger.info(f"Received file: {file.filename}")
    contents = await file.read()
    logger.info(f"File size: {len(contents)} bytes")
    # Input validation
    if not allowed_file(file.filename):
        logger.error(f"Invalid file type: {file.filename}")
        log_audit('upload_rejected', f'Invalid file type: {file.filename}')
        return JSONResponse(content={"error": "Invalid file type. Only CSV and Excel files are allowed."})
    if len(contents) > MAX_FILE_SIZE:
        logger.error(f"File too large: {file.filename} ({len(contents)} bytes)")
        log_audit('upload_rejected', f'File too large: {file.filename} ({len(contents)} bytes)')
        return JSONResponse(content={"error": "File too large. Max 5MB allowed."})
    # Try to parse file
    try:
        if file.filename.lower().endswith('.csv'):
            from io import StringIO
            df = pd.read_csv(StringIO(contents.decode('utf-8')), on_bad_lines='skip')
            sheets = {'CSV': df}
            logger.info(f"Parsed CSV file. Columns: {list(df.columns)}")
        else:
            from io import BytesIO
            excel_file = BytesIO(contents)
            excel_data = pd.read_excel(excel_file, sheet_name=None)
            logger.info(f"Excel sheets found: {list(excel_data.keys())}")
            sheets = {}
            for sheet_name, sheet_df in excel_data.items():
                # Replace inf and NaN with None for JSON serialization
                sheet_df = sheet_df.replace([np.inf, -np.inf], pd.NA)
                sheet_df = sheet_df.where(pd.notnull(sheet_df), None)
                sheets[sheet_name] = sheet_df
            if not sheets:
                logger.error("No sheets found in the uploaded Excel file.")
    except Exception as e:
        logger.error(f"Parse error: {file.filename} ({str(e)})")
        log_audit('upload_rejected', f'Parse error: {file.filename} ({str(e)})')
        return JSONResponse(content={"error": f"Could not parse file. The file may have inconsistent formatting. Try cleaning the CSV file or check for extra commas. Error: {str(e)}"})
    log_audit('upload', f'File uploaded: {file.filename} ({len(contents)} bytes)')
    last_processed_sheets = sheets

    # Per-sheet error detection and preview
    errors = {}
    preview = {}
    for name, df in sheets.items():
        sheet_errors = []
        # --- Context-aware: skip headers/non-postable accounts ---
        def is_header_row(row):
            # Heuristic: no account number, or account name is a known header
            known_headers = ['assets', 'liabilities', 'equity', 'revenue', 'expenses', 'contra revenue', 'contra asset', 'total', 'net income', 'gross profit', 'operating income']
            acc_name = str(row.get('Account', '')).strip().lower()
            acc_num = str(row.get('Account Number', '')).strip()
            if acc_name in known_headers or acc_name.startswith('total') or acc_num in ['', 'nan', 'none']:
                return True
            return False

        # Chart of Accounts: check for missing account numbers/names/types, duplicates
        if 'chart' in name.lower():
            if 'Account Number' in df.columns:
                missing_acc = df[df['Account Number'].isnull()]
                for idx in missing_acc.index:
                    sheet_errors.append({"row": idx+1, "issue": "Missing Account Number"})
            if 'Account Name' in df.columns:
                missing_name = df[df['Account Name'].isnull()]
                for idx in missing_name.index:
                    sheet_errors.append({"row": idx+1, "issue": "Missing Account Name"})
            if 'Type' in df.columns:
                missing_type = df[df['Type'].isnull()]
                for idx in missing_type.index:
                    sheet_errors.append({"row": idx+1, "issue": "Missing Account Type"})
            # Duplicates
            dups = df[df.duplicated()]
            for idx in dups.index:
                sheet_errors.append({"row": idx+1, "issue": "Duplicate row"})
        # Journal Entries: check for missing/invalid dates, unbalanced debits/credits, missing accounts, GAAP/IFRS rules
        elif 'journal' in name.lower():
            for idx, row in df.iterrows():
                if is_header_row(row):
                    continue
                # Date check
                if 'Date' in df.columns:
                    try:
                        pd.to_datetime(row['Date'])
                    except Exception:
                        sheet_errors.append({"row": idx+1, "issue": "Invalid or missing Date"})
                # Debit/Credit check
                debit = float(row['Debit']) if 'Debit' in df.columns and row['Debit'] not in [None, '', pd.NA] else 0
                credit = float(row['Credit']) if 'Credit' in df.columns and row['Credit'] not in [None, '', pd.NA] else 0
                if abs(debit - credit) > 0.01:
                    sheet_errors.append({"row": idx+1, "issue": f"Debit ({debit}) ≠ Credit ({credit})"})
                # Account check
                if 'Account' in df.columns and (row['Account'] is None or str(row['Account']).strip() == ''):
                    sheet_errors.append({"row": idx+1, "issue": "Missing Account"})
                # GAAP/IFRS rules
                acc_type = str(row.get('Type', '')).lower() if 'Type' in row else ''
                acc_name = str(row.get('Account', '')).lower()
                if acc_name == 'depreciation expense' and debit < 0:
                    sheet_errors.append({"row": idx+1, "issue": "Depreciation expense should not be negative (GAAP)"})
                if acc_type == 'revenue' and debit > 0:
                    sheet_errors.append({"row": idx+1, "issue": "Revenue account has debit value (GAAP)"})
                if acc_type == 'equity' and debit > 0:
                    sheet_errors.append({"row": idx+1, "issue": "Equity account should not have debit balance (GAAP)"})
                if acc_name == 'prepaid expenses' and 'income' in name.lower():
                    sheet_errors.append({"row": idx+1, "issue": "Prepaid expenses should not appear in P&L (GAAP)"})
        # Trial Balance: check for out-of-balance, missing accounts, auto-balance suggestion
        elif 'trial' in name.lower():
            if 'Debit' in df.columns and 'Credit' in df.columns:
                total_debit = pd.to_numeric(df['Debit'], errors='coerce').sum()
                total_credit = pd.to_numeric(df['Credit'], errors='coerce').sum()
                diff = total_debit - total_credit
                if abs(diff) > 1e-2:
                    # Suggest top 3 suspicious entries (nulls, high values)
                    suspicious = []
                    for idx, row in df.iterrows():
                        if pd.isnull(row['Debit']) or pd.isnull(row['Credit']) or abs(float(row['Debit'] or 0) - float(row['Credit'] or 0)) > 1000:
                            suspicious.append(idx+1)
                    suggestion = f"Consider checking rows: {', '.join(map(str, suspicious[:3]))}" if suspicious else "Review all entries."
                    sheet_errors.append({"row": None, "issue": f"Trial balance out of balance: Debits={total_debit}, Credits={total_credit}. Difference={diff}. {suggestion}"})
            if 'Account' in df.columns:
                missing_acc = df[df['Account'].isnull()]
                for idx in missing_acc.index:
                    sheet_errors.append({"row": idx+1, "issue": "Missing Account"})
        # Income Statement/Balance Sheet: check for missing/invalid formulas, missing values, skip headers
        elif 'income' in name.lower() or 'balance' in name.lower():
            for idx, row in df.iterrows():
                if is_header_row(row):
                    continue
                for col in df.columns:
                    if pd.isnull(row[col]):
                        sheet_errors.append({"row": idx+1, "issue": f"Missing value in {col}"})
                    # Formula audit
                    if isinstance(row[col], str) and row[col].startswith('='):
                        sheet_errors.append({"row": idx+1, "issue": f"Excel formula present in {col}: {row[col]} (Check for circular refs or hardcoded totals)"})
        errors[name] = sheet_errors
        preview[name] = {
            "columns": list(df.columns),
            "sample": df.head(5).to_dict(orient='records')
        }

    # --- Advanced: Cross-Sheet Reconciliation ---
    # Find key values for reconciliation
    net_income = None
    retained_earnings_change = None
    total_assets = None
    total_liab_equity = None
    for name, df in sheets.items():
        if 'income' in name.lower():
            # Try to find Net Income
            for idx, row in df.iterrows():
                if str(row.get('Account', '')).strip().lower() in ['net income', 'net profit']:
                    try:
                        net_income = float(row.get('Amount', 0))
                    except:
                        pass
        if 'balance' in name.lower():
            # Try to find Retained Earnings and totals
            for idx, row in df.iterrows():
                acc = str(row.get('Account', '')).strip().lower()
                if acc == 'retained earnings':
                    try:
                        retained_earnings_change = float(row.get('Amount', 0))
                    except:
                        pass
                if acc == 'total assets':
                    try:
                        total_assets = float(row.get('Amount', 0))
                    except:
                        pass
                if acc == 'total liabilities and equity':
                    try:
                        total_liab_equity = float(row.get('Amount', 0))
                    except:
                        pass
    # Add reconciliation errors if mismatches found
    if net_income is not None and retained_earnings_change is not None:
        if abs(net_income - retained_earnings_change) > 1e-2:
            errors.setdefault('Cross-Sheet', []).append({
                "row": None,
                "issue": f"Net income from Income Statement ({net_income}) does not match change in Retained Earnings on Balance Sheet ({retained_earnings_change})."
            })
    if total_assets is not None and total_liab_equity is not None:
        if abs(total_assets - total_liab_equity) > 1e-2:
            errors.setdefault('Cross-Sheet', []).append({
                "row": None,
                "issue": f"Total Assets ({total_assets}) does not equal Total Liabilities and Equity ({total_liab_equity}) on Balance Sheet."
            })

    # --- Advanced: Formula Audit ---
    for name, df in sheets.items():
        if 'income' in name.lower() or 'balance' in name.lower():
            for idx, row in df.iterrows():
                for col in df.columns:
                    val = row[col]
                    if isinstance(val, str) and val.startswith('='):
                        # Hardcoded total (e.g., =10000)
                        if val[1:].replace('.', '', 1).isdigit():
                            errors.setdefault(name, []).append({
                                "row": idx+1,
                                "issue": f"Formula in {col} is hardcoded value: {val}"
                            })
                        # Reference to empty cell (basic check)
                        if '""' in val or 'BLANK' in val.upper():
                            errors.setdefault(name, []).append({
                                "row": idx+1,
                                "issue": f"Formula in {col} references empty cell: {val}"
                            })
                        # Circular reference (very basic: formula references its own row)
                        if f'{col[0]}{idx+2}' in val:
                            errors.setdefault(name, []).append({
                                "row": idx+1,
                                "issue": f"Possible circular reference in {col}: {val}"
                            })

    # --- Audit Mode vs. Assist Mode (default: Audit) ---
    # You can add a query param ?mode=assist to switch to softer warnings
    import fastapi
    mode = 'audit'
    if isinstance(file, fastapi.datastructures.UploadFile) and hasattr(file, 'filename'):
        # Can't get query param here, but you can extend this logic to use a global or session
        pass
    # In assist mode, only show critical errors (e.g., out of balance, missing account)
    if mode == 'assist':
        for k in list(errors.keys()):
            errors[k] = [e for e in errors[k] if 'out of balance' in e['issue'].lower() or 'missing account' in e['issue'].lower()]

    return JSONResponse(content=clean_nans({
        "sheets": list(sheets.keys()),
        "preview": preview,
        "errors": errors
    }))

# Add the /bulk-fix endpoint after /upload

@app.post("/bulk-fix")
async def bulk_fix(
    fixes: str = Form(...),  # comma-separated list: 'auto-balance,fill-missing,remove-duplicates'
    sheet: str = Form(None)  # optional: which sheet to fix
):
    global last_processed_sheets
    if last_processed_sheets is None:
        return Response(json.dumps({"error": "No data loaded. Please upload a file first."}), status_code=400, media_type="application/json")
    
    applied = [f.strip() for f in fixes.split(',')]
    sheets_to_fix = [sheet] if sheet and sheet in last_processed_sheets else list(last_processed_sheets.keys())
    result = {}
    for name in sheets_to_fix:
        df = last_processed_sheets[name].copy()
        summary = []
        if 'remove-duplicates' in applied:
            before = len(df)
            df = df.drop_duplicates()
            after = len(df)
            summary.append(f"Removed {before - after} duplicate rows.")
        if 'fill-missing' in applied:
            num_missing = df.isnull().sum().sum()
            df = df.fillna(0)
            summary.append(f"Filled {num_missing} missing values with 0.")
        if 'auto-balance' in applied and 'Debit' in df.columns and 'Credit' in df.columns:
            for idx, row in df.iterrows():
                try:
                    debit = float(row['Debit']) if row['Debit'] not in [None, "", pd.NA] else 0
                    credit = float(row['Credit']) if row['Credit'] not in [None, "", pd.NA] else 0
                except (ValueError, TypeError):
                    continue
                if pd.isnull(debit) or pd.isnull(credit):
                    continue
                diff = debit - credit
                if abs(diff) <= 1e-2 and diff != 0:
                    if debit > credit:
                        df.at[idx, 'Credit'] = debit
                    else:
                        df.at[idx, 'Debit'] = credit
            summary.append("Auto-balanced small rounding errors (≤ 1 cent).")
        # Clean NaN/inf for JSON
        df = df.replace([np.inf, -np.inf], pd.NA)
        df = df.where(pd.notnull(df), None)
        # Update global
        last_processed_sheets[name] = df.copy()
        result[name] = {
            "fixed_entries": df.head(5).to_dict(orient='records'),
            "summary": summary,
            "columns": list(df.columns)
        }
    log_audit('bulk_fix', f'Fixes applied: {fixes} to sheets: {sheets_to_fix}')
    return JSONResponse(content=clean_nans(result))

# Add a new endpoint for CSV download

@app.get("/download-csv")
def download_csv(sheet: str = None):
    if last_processed_sheets is None:
        return Response("No data available for download.", status_code=404)
    if sheet and sheet in last_processed_sheets:
        stream = io.StringIO()
        last_processed_sheets[sheet].to_csv(stream, index=False)
        stream.seek(0)
        return StreamingResponse(stream, media_type="text/csv", headers={
            "Content-Disposition": f"attachment; filename={sheet.replace(' ', '_')}.csv"
        })
    # If no sheet specified, zip all sheets
    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, df in last_processed_sheets.items():
            csv_bytes = df.to_csv(index=False).encode('utf-8')
            zf.writestr(f"{name.replace(' ', '_')}.csv", csv_bytes)
    mem_zip.seek(0)
    return StreamingResponse(mem_zip, media_type="application/zip", headers={
        "Content-Disposition": "attachment; filename=ledgerlift_export.zip"
    })

@app.post("/analyze-excel-sheets")
async def analyze_excel_sheets(file: UploadFile = File(...)):
    """Analyze Excel file to show available sheets without processing data"""
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        return {"error": "This endpoint only works with Excel files (.xlsx, .xls)"}
    
    try:
        contents = await file.read()
        excel_file = BytesIO(contents)
        excel_data = pd.read_excel(excel_file, sheet_name=None)
        
        sheets_info = []
        for sheet_name, sheet_df in excel_data.items():
            sheets_info.append({
                "name": sheet_name,
                "rows": len(sheet_df),
                "columns": len(sheet_df.columns),
                "column_names": list(sheet_df.columns)
            })
        
        return {
            "total_sheets": len(excel_data),
            "sheets": sheets_info
        }
    except Exception as e:
        return {"error": f"Could not analyze Excel file: {str(e)}"}

# Placeholder for Excel export (future)
# @app.get("/download-excel")
# def download_excel():
#     global last_processed_df
#     if last_processed_df is None:
#         return Response("No data available for download.", status_code=404)
#     stream = io.BytesIO()
#     last_processed_df.to_excel(stream, index=False)
#     stream.seek(0)
#     return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={
#         "Content-Disposition": "attachment; filename=ledgerlift_export.xlsx"
#     })

@app.post("/custom-errors")
async def custom_errors(request: Request):
    data = await request.json()
    sheet = data.get("sheet")
    df = get_sheet(sheet)
    if df is None:
        return {"custom_errors": []}
    rules = data.get("rules", [])
    custom_errors = []
    for rule in rules:
        col = rule.get("column")
        cond = rule.get("condition")
        val = rule.get("value")
        if col not in df.columns:
            continue
        for idx, row in df.iterrows():
            cell = row[col]
            match = False
            try:
                if cond == ">":
                    match = float(cell) > float(val)
                elif cond == "<":
                    match = float(cell) < float(val)
                elif cond == ">=":
                    match = float(cell) >= float(val)
                elif cond == "<=":
                    match = float(cell) <= float(val)
                elif cond == "==":
                    match = str(cell) == str(val)
                elif cond == "!=":
                    match = str(cell) != str(val)
                elif cond == "empty":
                    match = cell is None or str(cell).strip() == "" or (isinstance(cell, float) and pd.isnull(cell))
                elif cond == "notempty":
                    match = not (cell is None or str(cell).strip() == "" or (isinstance(cell, float) and pd.isnull(cell)))
            except Exception:
                continue
            if match:
                custom_errors.append({"row": idx+1, "issue": f"Custom rule: {col} {cond} {val if val else ''}"})
    return JSONResponse(content=clean_nans({"custom_errors": custom_errors}))

@app.post("/edit-cell")
async def edit_cell(request: Request):
    data = await request.json()
    sheet = data.get("sheet")
    df = get_sheet(sheet)
    if df is None:
        return {"success": False, "error": "No data loaded."}
    row = data.get("row")
    column = data.get("column")
    value = data.get("value")
    try:
        if column in df.columns and 0 <= row < len(df):
            df.at[row, column] = value
            log_audit('edit_cell', f'Sheet {sheet}, Row {row}, Column {column}, Value {value}')
            last_processed_sheets[sheet] = df
            return {"success": True}
        else:
            return {"success": False, "error": "Invalid row or column."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/bulk-fix-preview")
async def bulk_fix_preview(request: Request):
    data = await request.json()
    sheet = data.get("sheet")
    fixes = data.get("fixes", [])
    df = get_sheet(sheet)
    if df is None:
        return {"preview": ["No data loaded."]}
    preview = []
    if 'remove-duplicates' in fixes:
        before = len(df)
        after = len(df.drop_duplicates())
        preview.append(f"Would remove {before - after} duplicate rows.")
    if 'fill-missing' in fixes:
        num_missing = df.isnull().sum().sum()
        preview.append(f"Would fill {num_missing} missing values with 0.")
    if 'auto-balance' in fixes and 'Debit' in df.columns and 'Credit' in df.columns:
        count = 0
        for idx, row in df.iterrows():
            try:
                debit = float(row['Debit']) if row['Debit'] not in [None, "", pd.NA] else 0
                credit = float(row['Credit']) if row['Credit'] not in [None, "", pd.NA] else 0
            except (ValueError, TypeError):
                continue
            if pd.isnull(debit) or pd.isnull(credit):
                continue
            diff = debit - credit
            if abs(diff) <= 1e-2 and diff != 0:
                count += 1
        preview.append(f"Would auto-balance {count} small rounding errors (≤ 1 cent).")
    if not preview:
        preview.append("No changes would be made.")
    return JSONResponse(content=clean_nans({"preview": preview}))

@app.post("/financial-report")
async def financial_report(request: Request):
    data = await request.json()
    sheet = data.get("sheet")
    df = get_sheet(sheet)
    if df is None:
        return HTMLResponse("<h2>No data loaded.</h2>", status_code=400)
    errors = data.get("errors", [])
    fixes = data.get("fixes", [])
    summary = data.get("summary", [])
    # Generate a simple HTML report
    html = """
    <html><head><title>Financial Data Report</title></head><body>
    <h1>Financial Data Summary Report</h1>
    <h2>Fixes Applied</h2>
    <ul>
    """
    for fix in fixes:
        html += f"<li>{fix}</li>"
    html += "</ul>"
    html += "<h2>Errors</h2><ul>"
    for err in errors:
        html += f"<li>Row {err.get('row', '?')}: {err.get('issue', '')}</li>"
    html += "</ul>"
    html += "<h2>Summary</h2><ul>"
    for s in summary:
        html += f"<li>{s}</li>"
    html += "</ul>"
    html += "<h2>Data Preview</h2>"
    html += df.head(10).to_html(index=False)
    html += "</body></html>"
    return HTMLResponse(content=html, headers={"Content-Disposition": "attachment; filename=financial_report.html"})

# Helper function to send email using SMTP

def send_email(recipient, subject, body):
    smtp_host = os.environ.get('SMTP_HOST', 'smtp.example.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER', 'user@example.com')
    smtp_pass = os.environ.get('SMTP_PASS', 'password')
    sender = os.environ.get('SMTP_SENDER', smtp_user)
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content(body)
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, None
    except Exception as e:
        return False, str(e)

@app.post("/send-email")
async def send_email_endpoint(request: Request):
    data = await request.json()
    recipient = data.get('recipient')
    subject = data.get('subject', 'LedgerLift Notification')
    body = data.get('body', '')
    if not recipient or not body:
        return {"success": False, "error": "Recipient and body required."}
    ok, err = send_email(recipient, subject, body)
    if ok:
        return {"success": True}
    else:
        return {"success": False, "error": err}

# To use email notifications, set the following environment variables:
# SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SENDER (optional)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
