from bs4 import BeautifulSoup
from datetime import datetime
import requests
import random
import time
import re



HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
}


# Scrape list of job
def scrape_jobstreet(query="machine-learning-jobs", daterange=1, max_pages=10):
    jobs = []
    for page in range(1, max_pages + 1):
        # url = f"https://id.jobstreet.com/id/{query}?page={page}"
        url = f"https://id.jobstreet.com/{query}?page={page}&daterange={daterange}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        
        if resp.status_code != 200:
            print(f"Page {page}: status {resp.status_code}, stop")
            break
        
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select('article[data-testid="job-card"]')
        
        if not cards:
            print(f"Page {page}: no more jobs")
            break
        
        for card in cards:
            job_id = card.get("data-job-id")
            title_el = card.select_one('a[data-automation="jobTitle"]')
            company_el = card.select_one('a[data-automation="jobCompany"]')
            location_el = card.select_one('a[data-automation="jobLocation"]')
            salary_el = card.select_one('span[data-automation="jobSalary"]')
            desc_el = card.select_one('span[data-automation="jobShortDescription"]')
            date_el = card.select_one('div[data-automation="jobListingDate"] span')
            
            date_text = date_el.get_text(strip=True) if date_el else ""
            
            jobs.append({
                "job_id": job_id,
                "title": title_el.get_text(strip=True) if title_el else None,
                "company": company_el.get_text(strip=True) if company_el else None,
                "location": location_el.get_text(strip=True) if location_el else None,
                "salary": salary_el.get_text(strip=True) if salary_el else None,
                "description": desc_el.get_text(strip=True) if desc_el else None,
                "posted": date_text,
                "link": f"https://id.jobstreet.com/id/job/{job_id}" if job_id else None,
            })
        
        print(f"Page {page}: {len(cards)} jobs collected")
        time.sleep(random.uniform(1,2))

    return jobs


def scrape_job_detail(job_id):
    url = f"https://id.jobstreet.com/id/job/{job_id}"
    resp=requests.get(url, headers=HEADERS, timeout=15)
    
    if resp.status_code != 200:
        print(f"Job ID {job_id}: status {resp.status_code}, stop")
        return None
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    
    title_el = soup.select_one('h1[data-automation="job-detail-title"]')
    company_el = soup.select_one('span[data-automation="advertiser-name"]')
    location_el = soup.select_one('span[data-automation="job-detail-location"]')
    classification_el = soup.select_one('span[data-automation="job-detail-classifications"]')
    work_type_el = soup.select_one('span[data-automation="job-detail-work-type"]')
    salary_el = soup.select_one('span[data-automation="job-detail-salary"]')
    desc_el = soup.select_one('div[data-automation="jobAdDetails"]')
    posted_el = soup.find('span', string=re.compile(r'(Diposting|Posted)', re.IGNORECASE))

    return {
        "job_id": job_id,
        "title": title_el.get_text(strip=True) if title_el else None,
        "company": company_el.get_text(strip=True) if company_el else None,
        "location": location_el.get_text(strip=True) if location_el else None,
        "classification": classification_el.get_text(strip=True) if classification_el else None,
        "work_type": work_type_el.get_text(strip=True) if work_type_el else None,
        "salary": salary_el.get_text(strip=True) if salary_el else None,
        "full_description": desc_el.get_text(separator="\n", strip=True) if desc_el else None,
        "url": url,
        "posted": posted_el.get_text(strip=True) if posted_el else None
    }


# def scrape_all_jobs_with_detail(query="machine-learning-jobs", max_pages=10, daterange=1):
#     job_list = scrape_jobstreet(query=query, max_pages=max_pages, daterange=daterange)

#     detailed_jobs = []
#     for job in job_list:
#         if not job["job_id"]:
#             continue
#         detail = scrape_job_detail(job_id=job["job_id"])
#         if detail:
#             detailed_jobs.append(detail)
#         time.sleep(random.uniform(1,2))
    
#     return detailed_jobs


# import json
# if __name__ == "__main__":
#     all_jobs = scrape_jobstreet()
#     with open("all_jobs.json", "w", encoding="utf-8") as f:
#         json.dump(all_jobs, f, indent=2, ensure_ascii=False)
#     print (f"\nTotal: {len(all_jobs)} within 1 day ago")
#     for j in all_jobs:
#         print(f"job id {j.get('job_id', '')} and title {j.get('title', '')}")


# import json
# if __name__ == "__main__":
#     results = scrape_all_jobs_with_detail()
#     with open("all_jobs_and_details.json", "w", encoding="utf-8") as f:
#         json.dump(results, f, indent=2, ensure_ascii=False)