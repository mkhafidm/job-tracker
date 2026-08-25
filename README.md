# Job Scraper — JobStreet (SEEK) Pipeline

Automated daily scraper + weekly analytics for JobStreet Indonesia, built with FlareSolverr, Groq LLM, and Google Sheets.

## Architecture
- **Scraper:** FlareSolverr bypass for Cloudflare, `SEEK_APOLLO_DATA` extraction, paginated search + detail pages
- **Summarizer:** Groq `qwen/qwen3.6-27b` extracts core requirements (tools/tech) from descriptions
- **Sheets:** `gspread` appends to `GRANDLINE` → `Job Screener` (16 cols) + weekly analytics
- **Weekly Report:** Mon-Sun WIB, `pandas` + LLM 2-field classification (`Role Group` + `Seniority`), salary `avg+median` IDR-only, city normalization, 5 stacked sections

> Scraper implementation is intentionally redacted in this public repo. See `core/scraper.py.example` for module interface and `specs/weekly-report-spec.md` for full architecture & design rationale. Full implementation available on request — reach out via [LinkedIn/email].

## Weekly Report — 5 Sections (1 Tab `Weekly YYYY-MM-DD_YYYY-MM-DD`)
1. **Demand Ranking** — 4 relevant groups × 3 seniority (Intern/Standard/Senior/Lead) + Total/%
2. **Salary by Role & City** — long format per Role Group: `City Norm | Seniority | Count | Avg | Median | Role Asli | Company` (City Norm: Jakarta, Unknown; `Count` IDR only, `Role Asli/Company` joined `; ` cap 3)
3. **Requirements per Role** — LLM top up to 10 hard skills per group
4. **Career Ladder** — 5 groups × 3 seniority, Count/Avg/Median IDR
5. **Other Roles Radar** — `Role Title | City Norm | Company` (3 cols, `Other` only)

## Usage
```bash
# Daily pipeline
python main.py

# Weekly report (now or mock date)
python weekly_main.py
python weekly_main.py --reference-date "2026-08-22"
```

## Config
Root `config.py` — `WIB`, `GRANDLINE`, `Job Screener`, `GROQ_API_KEY` via `.env` (not hardcoded), `CANONICAL_GROUPS` 5, `SENIORITY_GROUPS` 3

## Spec
See `specs/weekly-report-spec.md` — final locked source of truth (Mon-Sun flexible, City Norm only Sections 2 & 5, long/stacked, currency-count sync).

