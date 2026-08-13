import re
import json
import requests
import os
import time
import random
from bs4 import BeautifulSoup



FLARESOLVERR_URL = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1")


# HELPER
def fetch_via_flaresolverr(url, timeout=90000):
    resp = requests.post(FLARESOLVERR_URL, json={
        "cmd": "request.get",
        "url": url,
        "maxTimeout": timeout
    }, timeout=timeout / 1000 + 30)
    data = resp.json()
    if data.get("status") != "ok":
        print(f"FlareSolverr failed for {url}: {data.get('message')}")
        return None
    return data["solution"]["response"]


def extract_apollo_data(html):
    match = re.search(r'window\.SEEK_APOLLO_DATA\s*=\s*(\{.*?\});\s*\n', html, re.DOTALL)
    if not match:
        return None
    return json.loads(match.group(1))


def resolve_ref(apollo_data, ref):
    """Ambil object asli dari referensi {'__ref': 'Key:id'}"""
    if not ref or "__ref" not in ref:
        return None
    return apollo_data.get(ref["__ref"])


def get_text_safe(soup, automation_key):
    el = soup.find(attrs={"data-automation": automation_key})
    return el.get_text(separator=" ", strip=True) if el else None


# SCRAPE SEARCH PAGE
def scrape_search_page(query="machine-learning-jobs", daterange=1, max_pages=10):
    jobs = []
    for page in range(1, max_pages + 1):
        url = f"https://id.jobstreet.com/{query}?page={page}&daterange={daterange}"
        html = fetch_via_flaresolverr(url)

        if html is None:
            print(f"Page {page}: fetch failed, stop")
            break

        apollo_data = extract_apollo_data(html)
        if apollo_data is None:
            print(f"Page {page}: apollo data not found, stop")
            break

        root_query = apollo_data.get("ROOT_QUERY", {})
        job_search_key = next((k for k in root_query if k.startswith("jobSearchV7(")), None)

        if not job_search_key:
            print(f"Page {page}: no job search data")
            break

        raw_jobs = root_query[job_search_key].get("results", {}).get("jobs", [])

        if not raw_jobs:
            print(f"Page {page}: no more jobs")
            break

        for job in raw_jobs:
            job_id = job.get("id")
            location = resolve_ref(apollo_data, job.get("location"))
            salary = job.get("salary", {}) or {}

            jobs.append({
                "job_id": job_id,
                "title": job.get("title"),
                "company": job.get("advertiser", {}).get("name"),
                "location": location.get("displayName", {}).get("text") if location else None,
                "salary": salary.get("displayValue") or (
                    f"{salary.get('min')}-{salary.get('max')} {salary.get('currency')}"
                    if salary.get("min") and salary.get("max") else None
                ),
                "description": job.get("abstract"),
                "posted": job.get("listedAt", {}).get("dateTimeUtc"),
                "link": f"https://id.jobstreet.com/id/job/{job_id}" if job_id else None,
            })

        print(f"Page {page}: {len(raw_jobs)} jobs collected")
        time.sleep(random.uniform(1, 2))

    return jobs


# SCRAPE DETAIL JOB PAGE
def scrape_job_detail(job_id):
    detail_url = f"https://id.jobstreet.com/id/job/{job_id}"
    html = fetch_via_flaresolverr(detail_url)

    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")
    job_ad_div = soup.find("div", {"data-automation": "jobAdDetails"})
    
    return {
        "job_id": job_id,
        "title": get_text_safe(soup, "job-detail-title"),
        "company": get_text_safe(soup, "advertiser-name"),
        "location": get_text_safe(soup, "job-detail-location"),
        "work_type": get_text_safe(soup, "job-detail-work-type"),
        "classifications": get_text_safe(soup, "job-detail-classifications"),
        "full_description": job_ad_div.get_text(separator="\n", strip=True) if job_ad_div else None,
    }


# FINAL SCRAPE
def scrape_job_full(search_job_data):
    job_id = search_job_data["job_id"]
    detail = scrape_job_detail(job_id)

    if detail is None:
        return None

    return {
        "job_id": job_id,
        "title": detail.get("title") or search_job_data.get("title"),
        "company": detail.get("company") or search_job_data.get("company"),
        "location": detail.get("location") or search_job_data.get("location"),
        "classification": detail.get("classifications"),
        "work_type": detail.get("work_type"),
        "salary": search_job_data.get("salary"),
        "full_description": detail.get("full_description") or search_job_data.get("description"),
        "url": search_job_data.get("link"),
        "posted": search_job_data.get("posted"),
    }


if __name__ == "__main__":
    search = scrape_search_page()
    print(f"Total jobs from search: {len(search)}")

    jobs_full = []
    for i, job in enumerate(search, 1):
        print(f"[{i}/{len(search)}] Scraping detail: {job['title']} (id={job['job_id']})")
        full_job = scrape_job_full(job)
        if full_job:
            jobs_full.append(full_job)
        time.sleep(random.uniform(1, 2))

    print(f"Completed: {len(jobs_full)} / {len(search)}")

    with open("full_jobs.json", "w", encoding="utf-8") as f:
        json.dump(jobs_full, f, indent=2, ensure_ascii=False)
    print("Saved to jobs_full.json")