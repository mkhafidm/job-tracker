# Weekly Report — Mon-Sun WIB, 5 sections stacked
# Reads Job Screener sheet, classifies roles via LLM, aggregates salary/requirements

import re
import json
import pandas as pd
from groq import Groq

from config import (
    CANONICAL_GROUPS,
    SENIORITY_GROUPS,
    DATE_COLUMN,
    GROQ_API_KEY,
    GROQ_MODEL,
    REPORT_SHEET_PREFIX,
    SPREADSHEET_NAME,
    WIB,
    WORKSHEET_NAME,
)
from core.google_sheets import SHEET_HEADERS, get_gspread_client

_groq_client = None

def _get_groq():
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


# Week range: Monday 00:00 to Sunday 23:59 WIB
# Handles both naive ("2026-08-22") and aware ("2026-08-22 00:00+07:00") reference dates
def get_week_range(tz=WIB, reference_date=None) -> tuple[pd.Timestamp, pd.Timestamp]:
    if reference_date is None:
        now = pd.Timestamp.now(tz=tz)
    else:
        now = pd.Timestamp(reference_date)
        # naive vs aware: localize keeps wall time, convert shifts to target timezone
        if now.tz is None:
            now = now.tz_localize(tz)
        else:
            now = now.tz_convert(tz)
    monday = (now - pd.Timedelta(days=now.weekday())).normalize()
    sunday = monday + pd.Timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday, sunday


# Parse Posted Date column; strict "%d/%m/%Y" with fallback for manual edits like "2026-08-22"
def _parse_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, format="%d/%m/%Y", errors="coerce", dayfirst=True)
    mask = parsed.isna() & series.astype(str).str.strip().ne("") & series.notna()
    if mask.any():
        parsed.loc[mask] = pd.to_datetime(series.loc[mask], errors="coerce", dayfirst=True)
    return parsed


# Parse salary string "7000000-10000000 IDR" -> (mid, currency)
def _parse_salary(s: str) -> tuple[float | None, str | None]:
    if not s or not isinstance(s, str):
        return None, None
    s = s.strip()
    if not s or s.lower() == "nan":
        return None, None
    m = re.search(r"([\d.,\s]+)\s*-\s*([\d.,\s]+)\s*([A-Za-z$]+)?", s)
    if not m:
        return None, None
    def to_num(x):
        return int(re.sub(r"[^\d]", "", x))
    try:
        mn = to_num(m.group(1))
        mx = to_num(m.group(2))
        cur = (m.group(3) or "IDR").upper().strip()
        if "MYR" in cur:
            cur = "MYR"
        elif "USD" in cur or "$" in cur:
            cur = "USD"
        else:
            cur = "IDR"
        mid = (mn + mx) / 2
        return mid, cur
    except Exception:
        return None, None


# City normalization for aggregations (only Sections 2 & 5 use City Norm)
def _normalize_city(city: str) -> str:
    if not city or city.strip() in ("-", ""):
        return "Unknown"
    if city.strip().lower() == "indonesia":
        return "Unknown"
    if "jakarta" in city.lower():
        return "Jakarta"
    first = city.split(",")[0].strip()
    return first if first else "Unknown"


# Join Role/Company lists with cap for Section 2 traceback
def _join_list(values, limit=3):
    vals = [v for v in values if v and str(v).strip()]
    if not vals:
        return "-"
    if len(vals) > limit:
        return "; ".join(vals[:limit]) + f"; +{len(vals)-limit} others"
    return "; ".join(vals)


# Seniority fallback when LLM fails or returns invalid
def _classify_seniority_rule(title: str) -> str:
    low = title.lower() if isinstance(title, str) else ""
    if "intern" in low or "magang" in low:
        return "Intern"
    if any(k in low for k in ["senior", "lead", "principal", "head", "manager", "staff"]):
        return "Senior/Lead"
    return "Standard"


# LLM classification: distinct titles -> {Role Group, Seniority} (1 Groq call, ~12 titles)
def classify_roles_via_llm(roles: list[str]) -> dict[str, dict[str, str]]:
    if not roles:
        return {}
    distinct = sorted(set(r for r in roles if r and isinstance(r, str) and r.strip()))
    if not distinct:
        return {}
    canonical_str = ", ".join(CANONICAL_GROUPS)
    seniority_str = ", ".join(SENIORITY_GROUPS)
    try:
        prompt = f"""Classify each job title into Role Group and Seniority.

Canonical Role Groups: {canonical_str}
Seniority groups: {seniority_str}
Rules:
- AI/ML Engineer includes Machine Learning, LLM, AI Automation, AI Specialist
- Data Engineer includes Data Platform, ETL, Data Architect
- Data Scientist/Analyst includes Data Scientist, Data Analyst, BI, Analytics
- Seniority: Intern if contains intern/magang, Senior/Lead if senior/lead/principal/head/manager/staff, else Standard

Job titles:
{json.dumps(distinct, ensure_ascii=False, indent=2)}

Return ONLY valid JSON mapping: {{"raw title": {{"Role Group": "Canonical", "Seniority": "Seniority"}}, ...}} No explanation."""
        resp = _get_groq().chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=GROQ_MODEL,
            temperature=0.1,
            reasoning_effort="none",
            response_format={"type": "json_object"},
        )
        mapping = json.loads(resp.choices[0].message.content)
        result = {}
        for k, v in mapping.items():
            if not isinstance(v, dict):
                v = {"Role Group": str(v).strip(), "Seniority": _classify_seniority_rule(k)}
            rg = v.get("Role Group", "Other")
            sen = v.get("Seniority", _classify_seniority_rule(k))
            rg = rg.strip() if isinstance(rg, str) else "Other"
            sen = sen.strip() if isinstance(sen, str) else "Standard"
            if rg not in CANONICAL_GROUPS:
                for cand in CANONICAL_GROUPS:
                    if cand.lower() == rg.lower():
                        rg = cand
                        break
                else:
                    rg = "Other"
            if sen not in SENIORITY_GROUPS:
                for cand in SENIORITY_GROUPS:
                    if cand.lower() == sen.lower():
                        sen = cand
                        break
                else:
                    sen = _classify_seniority_rule(k)
            result[k] = {"Role Group": rg, "Seniority": sen}
        for r in distinct:
            if r not in result:
                result[r] = {"Role Group": "Other", "Seniority": _classify_seniority_rule(r)}
        return result
    except Exception as e:
        print(f"LLM classify failed, fallback: {e}")
        return {r: {"Role Group": "Other", "Seniority": _classify_seniority_rule(r)} for r in distinct}


# LLM summarize: per Role Group top skills (max 10)
def summarize_requirements_per_role(df: pd.DataFrame, role_col: str = "Role Group") -> dict[str, str]:
    if df.empty or role_col not in df.columns or "Core Requirements" not in df.columns:
        return {}
    result = {}
    for group, sub in df.groupby(role_col):
        merged = ", ".join(sub["Core Requirements"].dropna().astype(str).str.strip())
        merged = merged.strip(" ,")
        if not merged:
            result[group] = "-"
            continue
        # Truncate to avoid token limit
        if len(merged) > 4000:
            merged = merged[:4000]
        try:
            prompt = f"""Summarize the core hard-skill requirements for role group "{group}".
Input is comma-separated skills from multiple jobs: {merged}

INSTRUCTIONS:
- Return ONLY top up to 10 most frequent distinct tools/tech/hard skills, comma-separated single line. If many, max 10.
- No soft skills, no education, no numbering.
- Example: Python, SQL, GCP, TensorFlow, Docker"""
            resp = _get_groq().chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=GROQ_MODEL,
                temperature=0.2,
                reasoning_effort="none",
            )
            result[group] = resp.choices[0].message.content.strip()
        except Exception:
            parts = [p.strip() for p in merged.split(",") if p.strip()]
            from collections import Counter
            cnt = Counter(parts)
            result[group] = ", ".join([k for k, _ in cnt.most_common(10)]) if cnt else "-"
    return result


# Read full sheet as DataFrame
def read_sheet_as_dataframe(
    spreadsheet_name: str = SPREADSHEET_NAME,
    worksheet_name: str = WORKSHEET_NAME,
) -> pd.DataFrame:
    client = get_gspread_client()
    sh = client.open(spreadsheet_name)
    ws = sh.worksheet(worksheet_name)
    records = ws.get_all_records()
    if not records:
        return pd.DataFrame(columns=SHEET_HEADERS)
    df = pd.DataFrame(records)
    for col in SHEET_HEADERS:
        if col not in df.columns:
            df[col] = pd.NA
    return df


# Filter to current week Mon-Sun WIB
def read_jobs_this_week(
    spreadsheet_name: str = SPREADSHEET_NAME,
    worksheet_name: str = WORKSHEET_NAME,
    selected_columns: list[str] | None = None,
    date_column: str = DATE_COLUMN,
    reference_date=None,
) -> pd.DataFrame:
    df = read_sheet_as_dataframe(spreadsheet_name, worksheet_name)
    if df.empty or date_column not in df.columns:
        return df.iloc[0:0]
    df["_parsed"] = _parse_date_series(df[date_column].astype(str).replace("nan", ""))
    mon, sun = get_week_range(reference_date=reference_date)
    mon_naive = mon.tz_localize(None)
    sun_naive = sun.tz_localize(None)
    mask = df["_parsed"].between(mon_naive, sun_naive, inclusive="both")
    filtered = df.loc[mask].copy().drop(columns=["_parsed"])
    if selected_columns is not None:
        valid_cols = [c for c in selected_columns if c in filtered.columns]
        if valid_cols:
            filtered = filtered[valid_cols]
    return filtered.reset_index(drop=True)


# Main weekly aggregation — 5 sections + legacy fields
def weekly_report(
    spreadsheet_name: str = SPREADSHEET_NAME,
    worksheet_name: str = WORKSHEET_NAME,
    selected_columns: list[str] | None = None,
    date_column: str = DATE_COLUMN,
    reference_date=None,
    use_llm_classify: bool = True,
    use_llm_requirements: bool = True,
) -> dict:
    mon, sun = get_week_range(reference_date=reference_date)
    if reference_date is None:
        today = pd.Timestamp.now(tz=WIB)
    else:
        today = pd.Timestamp(reference_date)
        if today.tz is None:
            today = today.tz_localize(WIB)
        else:
            today = today.tz_convert(WIB)

    df = read_jobs_this_week(
        spreadsheet_name=spreadsheet_name,
        worksheet_name=worksheet_name,
        selected_columns=selected_columns,
        date_column=date_column,
        reference_date=reference_date,
    )

    # Classify Role Group + Seniority via LLM (distinct titles only)
    if not df.empty and "Role" in df.columns:
        roles = df["Role"].tolist()
        if use_llm_classify:
            mapping = classify_roles_via_llm(roles)
            df["Role Group"] = df["Role"].map(lambda r: mapping.get(r, {}).get("Role Group", "Other") if isinstance(mapping.get(r), dict) else mapping.get(r, "Other")).fillna("Other")
            df["Seniority"] = df["Role"].map(lambda r: mapping.get(r, {}).get("Seniority", _classify_seniority_rule(r)) if isinstance(mapping.get(r), dict) else _classify_seniority_rule(r)).fillna("Standard")
        else:
            df["Role Group"] = "Other"
            df["Seniority"] = df["Role"].apply(_classify_seniority_rule)

    if not df.empty and "Salary" in df.columns:
        parsed = df["Salary"].apply(_parse_salary)
        df["Salary Mid"] = [p[0] for p in parsed]
        df["Currency"] = [p[1] for p in parsed]

    # City Norm only for Sections 2 & 5; Sections 1,3,4 are Role×Seniority only
    # City Norm used only in Sections 2 & 5; Sections 1,3,4 are Role×Seniority only
    if not df.empty and "City" in df.columns:
        df["City Norm"] = df["City"].apply(_normalize_city)

    total = len(df)
    relevant = df[df["Role Group"] != "Other"] if "Role Group" in df.columns and not df.empty else df.iloc[0:0]
    total_relevant = len(relevant)

    # Section 1: Demand Ranking — 4 relevant groups, per seniority breakdown
    demand_ranking = pd.DataFrame()
    if total_relevant > 0:
        ct = pd.crosstab(relevant["Role Group"], relevant["Seniority"])
        for s in SENIORITY_GROUPS:
            if s not in ct.columns:
                ct[s] = 0
        ct = ct[SENIORITY_GROUPS]
        ct["Total"] = ct.sum(axis=1)
        ct["% Total"] = (ct["Total"] / total_relevant * 100).round(1)
        ct = ct.sort_values("Total", ascending=False)
        demand_ranking = ct.reset_index()

    # Section 2: Salary per Role × City (long format, IDR only, 7 cols)
    salary_long = pd.DataFrame()
    if total_relevant > 0 and "Salary Mid" in relevant.columns and "City Norm" in relevant.columns:
        groups = relevant.groupby(["Role Group", "City Norm", "Seniority"])
        rows = []
        for (rg, city, sen), sub in groups:
            idr_sub = sub[sub["Currency"] == "IDR"]
            cnt = len(idr_sub)
            if cnt == 0:
                continue
            if idr_sub["Salary Mid"].notna().any():
                avg = idr_sub["Salary Mid"].mean()
                med = idr_sub["Salary Mid"].median()
                avg = int(round(avg)) if pd.notna(avg) else "-"
                med = int(round(med)) if pd.notna(med) else "-"
            else:
                avg = "-"
                med = "-"
            role_asli = _join_list(idr_sub["Role"].tolist())
            company = _join_list(idr_sub["Company"].tolist())
            rows.append({"Role Group": rg, "City": city, "Seniority": sen, "Count": cnt, "Avg Salary": avg, "Median": med, "Role Asli": role_asli, "Company": company})
        salary_long = pd.DataFrame(rows).sort_values(["Role Group", "City", "Seniority"]).reset_index(drop=True) if rows else pd.DataFrame()

    # Section 3: Requirements per relevant Role Group (LLM, 5 calls)
    requirements_per_role = {}
    if total_relevant > 0 and "Role Group" in relevant.columns and use_llm_requirements:
        requirements_per_role = summarize_requirements_per_role(relevant)

    # Section 4: Career Ladder (5 groups, breakdown per seniority, IDR only)
    career_ladder = pd.DataFrame()
    if not df.empty and "Role Group" in df.columns and "Seniority" in df.columns:
        idr_all = df[df["Currency"] == "IDR"] if "Currency" in df.columns else df.iloc[0:0]
        if not idr_all.empty:
            cnt = pd.crosstab(idr_all["Role Group"], idr_all["Seniority"])
        else:
            cnt = pd.DataFrame(0, index=CANONICAL_GROUPS, columns=SENIORITY_GROUPS)
        for s in SENIORITY_GROUPS:
            if s not in cnt.columns:
                cnt[s] = 0
        for rg in CANONICAL_GROUPS:
            if rg not in cnt.index:
                cnt.loc[rg] = 0
        cnt = cnt.loc[CANONICAL_GROUPS, SENIORITY_GROUPS]
        if not idr_all.empty:
            grp = idr_all.groupby(["Role Group", "Seniority"])["Salary Mid"]
            avg = grp.mean().round(0)
            med = grp.median().round(0)
        else:
            avg = pd.Series(dtype=float)
            med = pd.Series(dtype=float)
        rows = []
        for rg in CANONICAL_GROUPS:
            for sen in SENIORITY_GROUPS:
                c = int(cnt.loc[rg, sen]) if rg in cnt.index and sen in cnt.columns else 0
                a = avg.get((rg, sen), None) if not avg.empty else None
                m = med.get((rg, sen), None) if not med.empty else None
                rows.append({"Role Group": rg, "Seniority": sen, "Count": c, "Avg Salary": int(a) if pd.notna(a) and a else "-", "Median": int(m) if pd.notna(m) and m else "-"})
        career_ladder = pd.DataFrame(rows)

    # Section 5: Other radar (3 cols)
    other_radar = pd.DataFrame()
    if not df.empty and "Role Group" in df.columns:
        other_radar = df[df["Role Group"] == "Other"][["Role", "City Norm", "Company"]].copy().rename(columns={"City Norm": "City"}) if "City Norm" in df.columns and "Company" in df.columns else pd.DataFrame()

    by_city = df["City"].value_counts(dropna=False).head(10).to_dict() if not df.empty and "City" in df.columns else {}
    by_role = df["Role"].value_counts(dropna=False).head(10).to_dict() if not df.empty and "Role" in df.columns else {}
    by_role_group = df["Role Group"].value_counts(dropna=False).to_dict() if not df.empty and "Role Group" in df.columns else {}
    by_seniority = df["Seniority"].value_counts(dropna=False).to_dict() if not df.empty and "Seniority" in df.columns else {}

    return {
        "filter_window": f"{mon:%d/%m/%Y} - {sun:%d/%m/%Y} (Mon-Sun WIB)",
        "data_up_to": f"{today:%A %d/%m/%Y} ({today:%H:%M} WIB)",
        "effective_data_range": f"{mon:%d/%m} - {today:%d/%m}" if today >= mon else f"{mon:%d/%m} - {sun:%d/%m}",
        "total_jobs_this_week": total,
        "total_relevant": total_relevant,
        "monday": mon,
        "sunday": sun,
        "today": today,
        "by_city_top10": by_city,
        "by_role_top10": by_role,
        "by_role_group": by_role_group,
        "by_seniority": by_seniority,
        "demand_ranking": demand_ranking,
        "salary_long": salary_long,
        "requirements_per_role": requirements_per_role,
        "career_ladder": career_ladder,
        "other_radar": other_radar,
        "data": df,
    }


# Save 5 stacked sections to new tab Weekly YYYY-MM-DD_YYYY-MM-DD
def save_weekly_report_to_sheet(
    report: dict | None = None,
    spreadsheet_name: str = SPREADSHEET_NAME,
    reference_date=None,
    worksheet_title: str | None = None,
) -> str:
    if report is None:
        report = weekly_report(spreadsheet_name=spreadsheet_name, reference_date=reference_date)

    mon = report["monday"]
    sun = report["sunday"]
    title = worksheet_title or f"{REPORT_SHEET_PREFIX} {mon:%Y-%m-%d}_{sun:%Y-%m-%d}"

    client = get_gspread_client()
    sh = client.open(spreadsheet_name)
    try:
        ws = sh.worksheet(title)
        ws.clear()
    except Exception:
        ws = sh.add_worksheet(title=title, rows=3000, cols=20)

    rows = []
    rows.append(["Metric", "Value"])
    rows.append(["Filter Window (Mon-Sun WIB)", report["filter_window"]])
    rows.append(["Data Up To", report["data_up_to"]])
    rows.append(["Effective Range", report["effective_data_range"]])
    rows.append(["Total Jobs This Week", report["total_jobs_this_week"]])
    rows.append(["Total Relevant (4 groups)", report.get("total_relevant", 0)])
    rows.append([])

    # Section 1 — Demand Ranking
    rows.append(["Section 1 — Demand Ranking", ""])
    demand = report.get("demand_ranking", pd.DataFrame())
    if demand.empty:
        rows.append(["No relevant role data this week"])
    else:
        rows.append(["Role Group", "Intern", "Standard", "Senior/Lead", "Total", "% Total"])
        for _, r in demand.iterrows():
            rows.append([r["Role Group"], int(r["Intern"]), int(r["Standard"]), int(r["Senior/Lead"]), int(r["Total"]), f"{r['% Total']}%"])
    rows.append([])

    # Section 2 — Salary by Role & City (long, 7 cols)
    rows.append(["Section 2 — Salary by Role & City", ""])
    salary_long = report.get("salary_long", pd.DataFrame())
    if salary_long.empty:
        if report.get("total_relevant", 0) == 0:
            rows.append(["No relevant role data this week"])
        else:
            rows.append(["No salary data this week"])
    else:
        for rg in sorted(salary_long["Role Group"].unique()):
            rows.append([f"Role Group: {rg}"])
            rows.append(["City", "Seniority", "Count", "Avg Salary", "Median", "Role Asli", "Company"])
            sub = salary_long[salary_long["Role Group"] == rg].sort_values(["City", "Seniority"])
            for _, r in sub.iterrows():
                avg = r["Avg Salary"] if r["Avg Salary"] != "-" and pd.notna(r["Avg Salary"]) else "-"
                med = r["Median"] if r["Median"] != "-" and pd.notna(r["Median"]) else "-"
                rows.append([r["City"], r["Seniority"], int(r["Count"]), avg, med, r.get("Role Asli", "-"), r.get("Company", "-")])
            rows.append([])
    if rows and rows[-1] == []:
        rows.pop()
    rows.append([])

    # Section 3 — Requirements per Role
    rows.append(["Section 3 — Requirements per Role", ""])
    req = report.get("requirements_per_role", {})
    if not req:
        if report.get("total_relevant", 0) == 0:
            rows.append(["No relevant role data this week"])
        else:
            rows.append(["-", "-"])
    else:
        for grp, skills in req.items():
            rows.append([grp, skills])
    rows.append([])

    # Section 4 — Career Ladder
    rows.append(["Section 4 — Career Ladder", ""])
    ladder = report.get("career_ladder", pd.DataFrame())
    if ladder.empty:
        rows.append(["-", "-", "-", "-", "-"])
    else:
        rows.append(["Role Group", "Seniority", "Count", "Avg Salary", "Median"])
        for _, r in ladder.iterrows():
            rows.append([r["Role Group"], r["Seniority"], int(r["Count"]), r["Avg Salary"], r["Median"]])
    rows.append([])

    # Section 5 — Other Roles Radar
    rows.append(["Section 5 — Other Roles Radar", ""])
    other = report.get("other_radar", pd.DataFrame())
    if other.empty:
        rows.append(["No Other roles this week"])
    else:
        rows.append(["Role Title", "City", "Company"])
        for _, r in other.iterrows():
            rows.append([r.get("Role",""), r.get("City",""), r.get("Company","")])

    max_cols = max(len(r) for r in rows) if rows else 2
    end_col = chr(ord("A") + max_cols - 1)
    ws.update(f"A1:{end_col}{len(rows)}", rows, value_input_option="USER_ENTERED")
    try:
        ws.format("A1:B1", {"textFormat": {"bold": True}})
    except Exception:
        pass
    return title


if __name__ == "__main__":
    print("=== get_week_range demo ===")
    for ref in [None, "2026-08-22", "2026-08-20"]:
        mon, sun = get_week_range(reference_date=ref)
        print(f"ref={ref!r} -> Mon {mon} | Sun {sun}")
    print("\n=== Mock LLM + salary test ===")
    mock = pd.DataFrame([
        {"Posted Date": "24/08/2026", "Company": "A", "Role": "AI Engineer - Jakarta", "City": "Jakarta", "Salary": "7000000-10000000 IDR", "Core Requirements": "Python, TensorFlow, GCP"},
        {"Posted Date": "24/08/2026", "Company": "B", "Role": "AI & Automation", "City": "Jakarta", "Salary": "12000000-15000000 IDR", "Core Requirements": "Python, LLM, Automation"},
        {"Posted Date": "24/08/2026", "Company": "C", "Role": "Data Engineer (Middle Level)", "City": "Bandung", "Salary": "8000000-12000000 IDR", "Core Requirements": "GCP, BigQuery, Python"},
    ])
    print("classify via LLM:", classify_roles_via_llm(mock["Role"].tolist()))
    print("salary parse:", [_parse_salary(s) for s in mock["Salary"]])
    print("\n=== Live ===")
    try:
        rpt = weekly_report()
        print(rpt["filter_window"], rpt["total_jobs_this_week"], rpt["by_role_group"])
        print("demand", rpt["demand_ranking"].to_string(index=False) if not rpt["demand_ranking"].empty else "empty")
        print("title", save_weekly_report_to_sheet(rpt))
    except Exception as e:
        print(f"Live failed: {e}")
        import traceback; traceback.print_exc()
