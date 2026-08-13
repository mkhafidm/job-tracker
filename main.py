from core.scraper import scrape_job_detail, scrape_jobstreet
from core.summarizer import summarize_description
from core.google_sheets import upload_jobs_to_gsheet
from core.proxy_handler import load_proxies, ProxyRotator, execute_with_retry, get_random_proxy
import time
import random



def run_pipeline(query="machine-learning-jobs", max_pages=10, daterange=1, spreadsheet_name="Project 2026", worksheet_name="Job Selection"):
    proxies = load_proxies("proxies/valid_proxies.txt")
    rotator = ProxyRotator(proxies)

    # Scrape job search
    job_list = execute_with_retry(
        scrape_jobstreet,
        rotator,
        max_retries=5,
        query=query,
        max_pages=max_pages,
        daterange=daterange
    )

    if not job_list:
        print("Failed to get job listing after retries. Pipeline stopped.")
        return

    # Scrape each job
    detailed_jobs = []
    for job in job_list:
        if not job["job_id"]:
            continue

        job_detail = execute_with_retry(
            scrape_job_detail,
            rotator,
            max_retries=3,
            job_id=job["job_id"]
        )

        if not job_detail:
            print(f"Skipping job {job['job_id']} after retries.")
            continue

        # Summarize description
        if job_detail.get("full_description"):
            core_requirements = summarize_description(job_detail["full_description"])
        else:
            print("Error Summarize")
            core_requirements = ""

        job_detail["core_requirements"] = core_requirements
        detailed_jobs.append(job_detail)

        time.sleep(random.uniform(1, 2))

    # Upload to spreadsheet
    if detailed_jobs:
        upload_jobs_to_gsheet(
            jobs=detailed_jobs,
            spreadsheet_name=spreadsheet_name,
            worksheet_name=worksheet_name
        )
        print(f"Uploaded {len(detailed_jobs)} jobs to Google Sheets.")
    else:
        print("No jobs to upload.")

    print(f"Pipeline Done. Total {len(detailed_jobs)} jobs processed")


if __name__=="__main__":
    run_pipeline()
