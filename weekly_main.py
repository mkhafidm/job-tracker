# Weekly report entry point — thin CLI over core.weekly_report

import argparse

from core.weekly_report import save_weekly_report_to_sheet, weekly_report


def main(reference_date=None):
    rpt = weekly_report(reference_date=reference_date)
    title = save_weekly_report_to_sheet(rpt)
    print(f"Filter Window : {rpt['filter_window']}")
    print(f"Data Up To    : {rpt['data_up_to']}")
    print(f"Total Jobs    : {rpt['total_jobs_this_week']} (Relevant: {rpt['total_relevant']})")
    print(f"By Role Group : {rpt['by_role_group']}")
    print(f"By Seniority  : {rpt['by_seniority']}")
    print(f"Saved to tab  : {title}")
    return title


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weekly Report — Mon-Sun WIB")
    parser.add_argument("--reference-date", dest="reference_date", default=None, help='Mock date e.g. "2026-08-22" or "2026-08-22 00:00+07:00"')
    args = parser.parse_args()
    main(reference_date=args.reference_date)
