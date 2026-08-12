from datetime import datetime, timedelta
import gspread
import re


gc = gspread.service_account(filename="credentials.json")

SHEET_HEADERS = [
    "Apply", "Tanggal Post", "Perusahaan", "Role", "Kota", "Source", "Via Kirim", "Versi CV",
    "Gaji Expec", "Core Requirements", "Requirements Gap", "Note", "Age", "URL", "Prioritas"
]

COLUMN_MAP = {
    "Apply": lambda j: False,                                    
    # "Tanggal Post": lambda j: j.get("posted", ""),
    "Tanggal Post": lambda j: parse_posted_date(j.get("posted", "")),                                       
    "Perusahaan": lambda j: j.get("company", ""),            
    "Role": lambda j: j.get("title", ""),                        
    "Kota": lambda j: j.get("location", ""),                    
    "Source": lambda j: "JobStreet",                             
    "Via Kirim": lambda j: "",
    "Versi CV": lambda j: "",
    "Gaji Expec": lambda j: j.get("salary", ""),                
    "Core Requirements": lambda j: j.get("core_requirements", ""), 
    "Requirements Gap": lambda j: "",
    "Note": lambda j: "",
    "Age": lambda j: "",
    "URL": lambda j: j.get("url", ""),                        
    "Prioritas": lambda j: ""                                
}


def parse_posted_date(posted_text, reference_time=None):
    if not posted_text:
        return ""

    ref = reference_time or datetime.now()
    text = posted_text.lower()

    if "baru saja" in text or "hari ini" in text:
        return ref.strftime("%d/%m/%Y")
    if "kemarin" in text:
        return (ref - timedelta(days=1)).strftime("%d/%m/%Y")

    match = re.search(r"(\d+)\s*(menit|jam|hari|minggu|bulan)", text)
    if not match:
        return posted_text

    value, unit = int(match.group(1)), match.group(2)
    delta = {
        "menit": timedelta(minutes=value),
        "jam": timedelta(hours=value),
        "hari": timedelta(days=value),
        "minggu": timedelta(weeks=value),
        "bulan": timedelta(days=value * 30),
    }[unit]

    return (ref - delta).strftime("%d/%m/%Y")


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

            worksheet.update(f"A{next_row}:O{end_row}", rows_to_append, value_input_option="USER_ENTERED")
            print(f"Success upload {len(rows_to_append)} data, start row {next_row}")

        # if rows_to_append:
        #     worksheet.append_rows(rows_to_append)
        #     print(f"Success upload {len(rows_to_append)} data to spreadsheet {spreadsheet_name}")
        else:
            print("No data to upload")


        return True
    
    except Exception as e:
        print(e)
        return False