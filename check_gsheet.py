import gspread
from oauth2client.service_account import ServiceAccountCredentials
import config
import os
from datetime import datetime

def test_gsheet():
    print("Testing Google Sheet Connection...")
    cred_file = getattr(config, 'GOOGLE_CREDENTIALS_FILE', 'credentials.json')
    sheet_url = getattr(config, 'GOOGLE_SHEET_URL', '')
    
    if not os.path.exists(cred_file):
        print(f"FAILED: {cred_file} not found.")
        return
    
    if not sheet_url:
        print("FAILED: GOOGLE_SHEET_URL not set in config.py.")
        return

    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(cred_file, scope)
        client = gspread.authorize(creds)
        
        print(f"Opening sheet: {sheet_url}")
        sheet = client.open_by_url(sheet_url).sheet1
        
        print("Successfully connected!")
        
        # Try to read headers
        headers = sheet.row_values(1)
        print(f"Existing headers: {headers}")
        
        # Try to append a test row
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_row = [timestamp, "Test", "discussions.unity.com", "http://test.com", "This is a diagnostic log test.", "TEST_ID"]
        
        print("Attempting to write test row...")
        sheet.append_row(test_row)
        print("SUCCESS: Test row added to Google Sheet!")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_gsheet()
