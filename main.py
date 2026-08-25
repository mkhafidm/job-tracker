# Daily pipeline: scrape -> summarize -> save -> upload to Google Sheets

from core.scraper import scrape_search_page, scrape_job_detail, scrape_job_full
from core.summarizer import summarize_description
from core.google_sheets import upload_jobs_to_gsheet
from datetime import datetime
import time
import random
import json
import os


def run_pipeline(query="machine-learning-jobs", daterange=1, max_pages=10, spreadsheet_name="GRANDLINE", worksheet_name="Job Screener"):
    list_job = scrape_search_page(query=query, daterange=daterange, max_pages=max_pages)
    print(f"Total job collected in range {daterange}: {len(list_job)}")

    all_detailed_job = []
    for i, job in enumerate(list_job):
        if not job['job_id']:
            continue

        print(f"[{i}/{len(list_job)}] Scraping detail: {job['title']} (id={job['job_id']})")
        detail_job = scrape_job_full(job)
        if not detail_job:
            print(f"Failed to scrape job_id={job['job_id']}")
            time.sleep(random.uniform(1, 2))
            continue

        if detail_job.get("full_description"):
            try:
                core_requirements = summarize_description(detail_job["full_description"])
            except Exception as e:
                print(f"Error summarize job_id={job['job_id']}: {e}")
                core_requirements = ""
        else:
            print("Error Summarize")
            core_requirements = ""

        detail_job["core_requirements"] = core_requirements
        all_detailed_job.append(detail_job)

        time.sleep(random.uniform(1, 2))

    print(f"Success {len(all_detailed_job)} / {len(list_job)}")

    # Persist locally and upload to Sheets
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"all_jobs_{timestamp}.json", "w", encoding="utf-8") as f:
        json.dump(all_detailed_job, f, indent=2, ensure_ascii=False)
    print("Saved to all_jobs_timestamp.json")

    success = upload_jobs_to_gsheet(jobs=all_detailed_job, spreadsheet_name=spreadsheet_name, worksheet_name=worksheet_name)
    if not success:
        print("WARNING: Failed upload data to spreadsheet")


if __name__ == "__main__":
    daterange = int(os.environ.get("DATERANGE", 1))
    max_pages = int(os.environ.get("MAX_PAGES", 10))
    run_pipeline(daterange=daterange, max_pages=max_pages)