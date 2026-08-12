from core.scraper import scrape_job_detail, scrape_jobstreet
from core.summarizer import summarize_description
from core.google_sheets import upload_jobs_to_gsheet
import time
import random



def run_pipeline(query="machine-learning-jobs", max_pages=10, daterange=1, spreadsheet_name="Project 2026", worksheet_name="Job Selection"):
    job_list = scrape_jobstreet(query=query, max_pages=max_pages, daterange=daterange)

    detailed_jobs = []
    for job in job_list:
        if not job["job_id"]:
            continue
        job_detail = scrape_job_detail(job_id=job["job_id"])
        if not job_detail:
            continue
        
        # Add key in detail job: core requirements
        if job_detail.get("full_description"):
            core_requirements = summarize_description(job_detail["full_description"])
        else:
            print("Error Summarize")
            core_requirements = ""

        job_detail["core_requirements"] = core_requirements
        if job_detail:
            detailed_jobs.append(job_detail)

        time.sleep(random.uniform(1,2))

    # Save ke spreadsheet
    upload_jobs_to_gsheet(
        jobs=detailed_jobs,
        spreadsheet_name=spreadsheet_name,
        worksheet_name=worksheet_name
    )

if __name__=="__main__":
    run_pipeline()
