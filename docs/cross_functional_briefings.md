# 🤝 Cross-Functional Communication

> The same data, told three different ways, for three different audiences.
> This file demonstrates the responsibility:
> *"Collaborate in cross-functional teams of product managers, engineering,
> and operations."*

---

## 1. 📩 For Engineering — Bug Report Template

**Audience:** Backend / Mobile / API engineers
**Tone:** precise, actionable, with logs and reproduction steps

> **Subject:** [DATA-QUALITY] Duplicate sleep records — root cause in iOS sync
> retry logic
>
> **Severity:** WARN (no data loss, but DQS dropped 1.2pp)
>
> **What we observed**
> Between 2026-04-08 and 2026-04-11, the `sleep_records` collection in
> `wellness_telemetry` accumulated 1,847 exact duplicates across 412 unique
> users. All duplicates share an identical `sleep_start` but different
> `_id` and `received_at` timestamps 60–120 s apart.
>
> **Root cause hypothesis**
> The iOS HealthKit background-fetch task is firing twice when the device
> sync exceeds the 30-second iOS background-task timeout. The second fire
> reposts the same payload before the first finishes. Confirmed by:
>
> ```python
> # notebooks/02_anomaly_investigation.ipynb, cell 14
> dups = mongo.detect_duplicate_sleep_records()
> dups.merge(ingestion_audit, on="request_id") \
>     .groupby("device_type")["count"].sum()
> #    fitbit         0
> #    apple_health  1847   ← all duplicates are iOS
> ```
>
> **Suggested fix**
> Move the dedupe key from `(user_id, _id)` to `(user_id, sleep_start)` on
> upsert in the API layer; add an idempotency token in the iOS client.
>
> **Files / logs attached**
> - `ingestion_audit` rows: `data/processed/dups_2026_04_11.parquet`
> - Failed-check log query: `SELECT * FROM clinical.data_quality_log
>   WHERE check_name = 'uniqueness::user_id+sleep_start';`

---

## 2. 📊 For Product Managers — Insight Briefing

**Audience:** Product Manager owning the Sleep Coaching feature
**Tone:** narrative, business outcome first, math hidden in appendix

> **TL;DR**
> Users who hit ≥ 7 h of sleep on at least 5 nights per week have a
> **23% higher 90-day retention** than users averaging < 6 h. The new
> "Sleep Streak" notification could be A/B tested against this cohort.
>
> **Three things to know**
>
> 1. **The sleep-engagement gap is real.** Median weekly sleep duration is
>    6 h 42 m across the platform, well below the 7 h CDC recommendation.
> 2. **A small intervention moves the needle.** Users who received a
>    "wind-down reminder" in our limited pilot increased their average
>    sleep by 14 minutes (95% CI: 9–19 min, n=412).
> 3. **The Apple-Health iOS bug** (see Engineering note) was inflating our
>    sleep numbers by ~3.4%. After the dedupe fix lands, the dashboard
>    will appear to "drop" — that's a correction, not a regression.
>
> **What I'd recommend**
> - A/B test a configurable wind-down reminder on the 18-34 age bracket
> - Track impact on `total_minutes` and `efficiency_pct`, not just
>   notification CTR
> - Hold the rollout until the iOS dedupe fix ships, to avoid confounding
>
> **Appendix — how the numbers were produced** is in
> `notebooks/03_dashboards.ipynb`, cell 8.

---

## 3. 🩺 For Operations / Clinical — Threshold Calibration Memo

**Audience:** Clinical Operations Lead
**Tone:** deferential to clinical judgment, asks specific questions

> **What I need from you**
> Confirmation or correction on the eight clinical thresholds we use to
> auto-flag records in the quality engine. These thresholds drive the
> `range::*` checks in `src/quality_engine/logic_rules.py`.
>
> **Current bounds**
>
> | Metric | Lower | Upper | Source |
> |---|---|---|---|
> | Systolic BP (mmHg) | 50 | 260 | AHA hypertensive-crisis guideline |
> | Diastolic BP (mmHg) | 30 | 160 | AHA hypertensive-crisis guideline |
> | Pulse rate (bpm) | 30 | 220 | resting → max HR formula |
> | Total cholesterol (mg/dL) | 50 | 500 | NCEP ATP III |
> | LDL (mg/dL) | 10 | 400 | NCEP ATP III |
> | Fasting glucose (mg/dL) | 30 | 600 | ADA |
> | HbA1c (%) | 3.0 | 20.0 | ADA |
> | BMI | 10 | 70 | WHO |
>
> **Specific questions**
> 1. Should we tighten the systolic upper bound? Our Z-score model flags a
>    consistent cluster around 200–220 mmHg that may be clinically real,
>    not device error.
> 2. Are there age-specific thresholds we should apply for pulse rate
>    (e.g., children vs. adults)?
> 3. How would you prefer outliers to be flagged in the data sent to your
>    care team — by raw value, by Z-score severity, or both?
>
> Let's review at the monthly threshold meeting.

---

## 📌 Why this matters

The hardest part of being a data analyst on a multi-disciplinary team isn't
the SQL or the statistics — it's translating the same underlying truth into
three different vocabularies without losing fidelity. The bullets in this
file should be considered templates; copy them into Slack / Jira / Confluence
as needed.
