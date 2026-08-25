# Central configuration for Job Scraper
# All tunable values are environment-driven with sensible defaults

import os
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

WIB = ZoneInfo("Asia/Jakarta")

SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "GRANDLINE")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "Job Screener")
DATE_COLUMN = os.getenv("DATE_COLUMN", "Posted Date")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE", "credentials.json")
REPORT_SHEET_PREFIX = os.getenv("REPORT_SHEET_PREFIX", "Weekly")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")

SENIORITY_GROUPS = ["Intern", "Standard", "Senior/Lead"]

CANONICAL_GROUPS = [
    "AI/ML Engineer",
    "Data Engineer",
    "Data Scientist/Analyst",
    "Software Engineer",
    "Other",
]
