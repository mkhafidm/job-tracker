# Weekly Report Spec — Job Scraper (Final Locked)

**Status:** Locked 2026-08-25 — source of truth before code. Code revisions only after senior/dev approval.
**Scope:** `GRANDLINE` → `Job Screener` → Weekly `GRANDLINE` new tab `Weekly YYYY-MM-DD_YYYY-MM-DD`
**Locked Decisions:**
1. `count=0 → Avg/Median "-"`, `count≥1 → show actual` (Count beside it serves as caveat, not hiding `n=1`)
2. Section 5 radar `Role Title | City | Company` (skip `Posted Date`, Mon-Sun filter already guarantees current week)
3. Spec document first, then code (`config.py` + `core/weekly_report.py`)

---

## 1. Goal & Context

Weekly pipeline summarizes 12 jobs/week (live 24-30 Aug 12 jobs) into 5 stacked sections in 1 new tab. Focus on levels `Intern / Standard / Senior/Lead` separated (not merging `Intern+Standard`), 4 relevant roles for analysis, `Other` as separate radar.

**Relevant Roles (4):** `AI/ML Engineer` (LLM/RAG/NLP/CV/ML), `Data Engineer` (ETL/pipeline/infra), `Data Scientist/Analyst` (merged BI+Analyst+Scientist), `Software Engineer`
**Other (1):** `Other` (MLOps/DevOps + remaining irrelevant) — exclude Sections 1-3, include Section 4 breakdown + Section 5 radar

---

## 2. Config (`config.py:1` root)

```python
WIB = ZoneInfo("Asia/Jakarta")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "GRANDLINE")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "Job Screener")
DATE_COLUMN = os.getenv("DATE_COLUMN", "Posted Date")
CREDENTIALS_FILE = "credentials.json"
REPORT_SHEET_PREFIX = "Weekly"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # via .env + load_dotenv, not hardcoded
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
CANONICAL_GROUPS = ["AI/ML Engineer","Data Engineer","Data Scientist/Analyst","Software Engineer","Other"]
SENIORITY_GROUPS = ["Intern","Standard","Senior/Lead"]
```

**Reason for 5 groups (not 7):** `Data Scientist` + `Data Analyst` merged (overlapping Data Science background), `MLOps/DevOps` → `Other` (skip for AI/DE career). 5 is more stable than 7 fragmented groups.

---

## 3. Data Flow

```
read_jobs_this_week() [core/weekly_report.py:195]
  -> get_week_range(tz=WIB, reference_date=None) [core/weekly_report.py:28]
       now = Timestamp.now(WIB) or Timestamp(reference_date) -> tz_localize/convert WIB
       monday = (now - weekday).normalize() 00:00, sunday = monday+6d 23:59:59
       window Mon-Sun flexible daily: Fri run 17-23 Aug -> Mon-Fri 5 rows, Sun 7 rows
  -> read_sheet_as_dataframe() [core/weekly_report.py:180] gspread ws.get_all_records() -> pd.DataFrame (SHEET_HEADERS 16 cols)
  -> _parse_date_series() [core/weekly_report.py:43] format "%d/%m/%Y" + fallback generic
  -> mask between(mon_naive, sun_naive) -> df filtered Mon-Sun

weekly_report(df) [core/weekly_report.py:218]
  -> classify_roles_via_llm(distinct Roles) [core/weekly_report.py:79] 1 Groq call, ~12 titles
       Prompt: Canonical 5 + Seniority 3 + Rules (AI/ML Engineer includes ML/LLM, etc.)
       Return {"raw": {"Role Group": "AI/ML Engineer", "Seniority": "Standard"}} + _classify_seniority_rule() fallback
       df["Role Group"], df["Seniority"]
  -> _normalize_city() [core/weekly_report.py:76] combination: Indonesia→Unknown, "jakarta" in city.lower()→Jakarta, else first part ("Surabaya, East Java"→Surabaya) -> df["City Norm"] (City Norm only in Sections 2 & 5, Sections 1,3,4 do not use City)
  -> _parse_salary() [core/weekly_report.py:52] regex (min-max currency) -> mid=(min+max)/2, Currency IDR/MYR/USD -> df["Salary Mid"], df["Currency"]
  -> _join_list() [core/weekly_report.py:84] join Role/Company with "; ", cap 3 + " +N others" for Section 2 traceback
  -> aggregates: by_city (City Norm), by_role, by_role_group, by_seniority, avg+median per City Norm/role (IDR only), city_role_matrix crosstab, requirements_per_role LLM 5 calls max 10

save_weekly_report_to_sheet(report) [core/weekly_report.py:310]
  -> title Weekly YYYY-MM-DD_YYYY-MM-DD (mon/sun)
  -> sh.worksheet(title) -> clear() else add_worksheet(rows=2000, cols=30)
  -> stacked 5 sections, ws.update(A1:Z, rows), bold header
```

**Toolstack:** `gspread 6.2.1`, `pandas 3.0.5` (to_datetime, between, groupby, crosstab), `Groq qwen/qwen3.6-27b` reasoning_effort="none" + json_object, `ZoneInfo`

---

## 4. Section Spec Detail (5 Sections, 1 Tab Stacked)

### Section 1 — Demand Ranking
**Source:** `df[df["Role Group"] != "Other"]` crosstab Role Group × Seniority
```
Role Group          | Intern | Standard | Senior/Lead | Total | % Total
AI/ML Engineer       | 0      | 2        | 1           | 3     | 30%
Data Engineer        | 1      | 3        | 0           | 4     | 40%
Data Scientist/Analyst| 1     | 0        | 0           | 1     | 10%
Software Engineer    | 0      | 1        | 0           | 1     | 10%
```
`Total` = sum of 3 seniorities, `%` = Total / total_relevant*100 (guard: if `total_relevant==0` → Sections 1-3 display `"No relevant role data this week"` without calculating %, no `ZeroDivision` crash). Other excluded.

### Section 2 — Salary by Role & City
**Per Role Group header → table City Norm | Seniority | Count | Avg Salary | Median | Role Title | Company** (Role Title before Company, more specific to the right, `count>=1` join all)
```
Role Group: Data Engineer
City     | Seniority | Count | Avg Salary | Median | Role Title                                     | Company
Jakarta   | Standard   | 3     | 10,033,333 | 11,250,000 | Data Engineer; Data Platform Eng; Data Infra    | PT A; PT B; PT C
Jakarta   | Intern     | 1     | 2,500,000  | 2,500,000  | Data Eng Jr.                                   | PT Saka Farma
Surabaya  | Standard   | 1     | 4,800,000  | 4,800,000  | Data Eng Middle                                | PT X
```
**Rules:** `count=0 → Avg/Median "-"` (filtered out, not displayed), `count≥1 → show actual` (Count serves as caveat); **Role Title/Company `count>=1` join all `"; "` via `_join_list(values, limit=3)` cap `+N others` if `>3`** (previously `count==1` only → blank for Standard which needs it most, now `count=3` still filled `a; b; c`). Long format 7 cols, not wide 10 cols (overflow) and not city-only split. `groupby(["Role Group","City Norm","Seniority"])["Salary Mid"]` IDR only mean+median, `City Norm` via `_normalize_city` + `_join_list` cap 3. **Count = Count IDR (sample for Avg/Median, not total jobs)** — `Data Engineer Jakarta Standard` with `2 IDR +1 MYR` → `Count 2` (IDR only) synchronized `Avg from 2`, MYR remains in Section 1 `Total 12`.

### Section 3 — Requirements per Role
**Source:** `df_level = df[df["Role Group"] != "Other"]` groupby Role Group concat Core Requirements truncate 4000 → LLM `top up to 10 distinct hard skills, comma-separated, max 10` (previously 5-7) → fallback Counter.most_common(10)
```
Role Group: Data Engineer
Top Skills: Python, SQL, Airflow, ETL, GCP, BigQuery, dbt, Looker, Docker, Kubernetes (max 10)
```
5 calls all-seniority (not 15 per seniority, `n=12/5/3 <1` not reliable)

### Section 4 — Career Ladder
```
Role Group       | Seniority   | Count | Avg Salary | Median
Data Engineer    | Intern      | 1     | 2,500,000  | 2,500,000
Data Engineer    | Standard    | 3     | 5,800,000  | 5,900,000
Data Engineer    | Senior/Lead | 0     | -          | -
AI/ML Engineer   | Intern      | 0     | -          | -
AI/ML Engineer   | Standard    | 2     | 4,900,000  | 4,900,000
AI/ML Engineer   | Senior/Lead | 1     | 15,000,000 | 15,000,000
Other            | Intern      | 0     | -          | -
Other            | Standard    | 2     | 7,200,000  | 7,200,000
Other            | Senior/Lead | 0     | -          | -
```
`groupby(["Role Group","Seniority"])` count IDR only + mean/median IDR — **Other remains broken down per seniority (1-3 rows) like other roles, not 1 aggregated row.** Count = Count IDR synchronized Avg/Median. If Other only exists in 1 seniority this week, other 2 rows display `0 | - | -` for consistency.

### Section 5 — Other Roles Radar
**Source:** `df[df["Role Group"]=="Other"][["Role","City Norm","Company"]]` ~2 rows (`City Norm` via `_normalize_city`)
```
Role Title       | City Norm | Company
Product Manager   | Jakarta   | PT XYZ
QA Engineer       | Surabaya  | PT ABC
```
Skip Salary/Requirements, skip Posted Date (Mon-Sun filter already guarantees). Different from old Detail Jobs full table which was dropped (previously 12 rows with Salary/Core Requirements).

---

## 5. Save Layout (1 Tab Stacked Vertically)

```
A1: Metric | Value
A2: Filter Window (Mon-Sun WIB) | 24/08/2026 - 30/08/2026
A3: Total Jobs This Week | 12
Section 1 Demand Ranking (4 relevant)
Section 2 Salary by Role & City (long, per Role Group)
Section 3 Requirements per Role (4 relevant)
Section 4 Career Ladder (5 groups, Other breakdown per seniority)
Section 5 Other Roles Radar (3 cols)
Detail table: Dropped — no separate Detail table. Section 5 radar is sufficient for Other, Sections 1-4 cover 4 relevant groups. Original Job Screener sheet remains the detail source.
```

`ws.update(f"A1:{end_col}{len(rows)}", rows)`, `max_cols = max(len(r))`, `bold` header, `cols=30` sufficient for 7 cols long.

---

## 6. Validation (Live 24-30 Aug — Re-validated 5-Group)

*   `by_role_group={'Data Engineer':4,'AI/ML Engineer':3,'Software Engineer':2,'Other':2,'Data Scientist/Analyst':1}` (5-group: `AI Engineer→AI/ML Engineer`, `Data Analyst→Data Scientist/Analyst`, `MLOps→Other`)
*   `by_seniority={'Standard':9,'Intern':2,'Senior/Lead':1}` (Intern: `Tech Developer Intern` + `Internal Audit Assistant Manager`→Intern, Senior/Lead: `LEAD AI SENIOR MACHINE LEARNING`)
*   Salary Jakarta avg 6,915,306 median 7,345,000 (mean vs median outlier `60jt-100jt`)
*   Mock `AI Engineer - Jakarta→AI/ML Engineer Standard`, `Tech Developer Intern→Software Engineer Intern` via LLM 2-field `qwen/qwen3.6-27b`
*   **Guard:** If `total_relevant==0` (all Other/empty) → Sections 1-3 display `"No relevant role data this week"` without calculating `%` (avoid `ZeroDivision`), Section 4 still shows `Other` breakdown, Section 5 radar remains (may be empty)
*   **Note:** Numbers above re-validated after prompt update 7→5-group (previously stale `AI Engineer`/`Data Analyst` separate)

---

## 7. Next Steps

1. Update `config.py:1` 7→5 groups
2. Patch `core/weekly_report.py:79` 2-field prompt + `weekly_report()` 5 sections + `save` stacked
3. Add `pandas` to `requirements.txt` if not present
4. `weekly_main.py` CLI + `.github/workflows/weekly.yml` cron Mon 07:00 WIB (optional A)
