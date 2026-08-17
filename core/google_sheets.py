from datetime import datetime, timedelta
import gspread
import re


gc = gspread.service_account(filename="credentials.json")

SHEET_HEADERS = [
    "Apply", "Posted Date", "Company", "Role", "City", "Source", "Send via", "CV Version",
    "Salary", "Salary Expectation", "Core Requirements", "Requirements Gap", "Note", "Age", "URL", "Priority"
]

COLUMN_MAP = {
    "Apply": lambda j: False,                                    
    "Posted Date": lambda j: parse_posted_date(j.get("posted", "")),                                       
    "Company": lambda j: j.get("company", ""),            
    "Role": lambda j: j.get("title", ""),                        
    "City": lambda j: j.get("location", ""),                    
    "Source": lambda j: "JobStreet",                             
    "Send via": lambda j: "",
    "CV Version": lambda j: "",
    "Salary": lambda j: j.get("salary", ""),   
    "Salary Expectation": lambda j: "",              
    "Core Requirements": lambda j: j.get("core_requirements", ""), 
    "Requirements Gap": lambda j: "",
    "Note": lambda j: "",
    "Age": lambda j: "",
    "URL": lambda j: j.get("url", ""),                        
    "Priority": lambda j: ""                                
}


def parse_posted_date(posted_iso, reference_time=None):
    if not posted_iso:
        return ""
    try:
        dt = datetime.fromisoformat(posted_iso.replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError) as e:
        print(f"Gagal parse tanggal: {posted_iso} - {e}")
        return posted_iso


def upload_jobs_to_gsheet(jobs:list, spreadsheet_name, worksheet_name):
    try:
        sh = gc.open(spreadsheet_name)
        worksheet = sh.worksheet(worksheet_name)

        # Add data based on column map
        rows_to_append = []
        for job in jobs:
            row = []
            for col_name in SHEET_HEADERS:
                extractor = COLUMN_MAP.get(col_name)
                if extractor:
                    value = extractor(job) # run lambda function
                else:
                    value = ""
                row.append(value)
            rows_to_append.append(row)
        
        if rows_to_append:
            # find next row using column C
            col_values = worksheet.col_values(3)
            next_row = len(col_values) + 1
            end_row = next_row + len(rows_to_append) - 1

            worksheet.update(f"A{next_row}:P{end_row}", rows_to_append, value_input_option="USER_ENTERED")
            print(f"Success upload {len(rows_to_append)} data, start row {next_row}")

        else:
            print("No data to upload")


        return True
    
    except Exception as e:
        print(e)
        return False