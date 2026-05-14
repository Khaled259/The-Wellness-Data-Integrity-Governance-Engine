# 🛡️ Data Governance Policy

> Defines **how health data is stored, accessed, and anonymized** in the
> Wellness Data Integrity Engine. This document is the human-readable
> counterpart to `src/governance/anonymizer.py`.

**Version:** 1.0 · **Effective date:** 2026-Q2 · **Owner:** Data Analyst

---

## 1. Scope

This policy applies to all data flowing through the pipeline, including:

- NHANES clinical data in `clinical.*` (PostgreSQL)
- Wearable telemetry in `wellness_telemetry.*` (MongoDB)
- Any derived datasets in `data/processed/`

It does **not** apply to fully aggregated, non-identifiable metrics (e.g.
"average daily steps across all users in a survey wave").

---

## 2. Data Classification

Every column is tagged in `docs/data_dictionary.md` with one of four levels:

| Level | Examples | Who can read it |
|---|---|---|
| `public` | survey cycle, gender, derived risk tier | anyone, including third-party reports |
| `internal` | row IDs, ingestion timestamps, FK pseudonyms | any employee |
| `sensitive` | blood pressure, lab results, HR, sleep stages | analysts + engineers + clinical ops |
| `restricted` | raw email, raw device ID, geolocation | admins only |

Enforcement: see `src/governance/anonymizer.py::role_can_read`.

---

## 3. PII Handling Rules

### 3.1 Direct identifiers — **always pseudonymized**
- Names, emails, phone numbers, raw device IDs, MAC addresses, IMEIs, SSNs
- Replacement: salted SHA-256, truncated to 16 hex chars
- Salt rotated annually; rotation requires re-keying the join tables

### 3.2 Quasi-identifiers — **generalized**
- **Age:** capped at 89 (HIPAA Safe Harbor §164.514(b)(2)(i)(C))
- **ZIP code:** truncated to 3 digits, blanked entirely for low-population
  ZIPs (per §164.514(b)(2)(i)(B))
- **Dates of birth:** dropped from analytics tables; only `age_years` retained

### 3.3 Geolocation
- Latitude/longitude rounded to 2 decimal places (~1.1 km precision)
- Removed entirely if combined with health data unless aggregated to ≥50 users

---

## 4. Role-Based Access Control (RBAC)

```
admin     ─► public ✅  internal ✅  sensitive ✅  restricted ✅
engineer  ─► public ✅  internal ✅  sensitive ✅  restricted ❌
analyst   ─► public ✅  internal ✅  sensitive ❌  restricted ❌
intern    ─► public ✅  internal ❌  sensitive ❌  restricted ❌
```

- Roles are assigned in PostgreSQL via `GRANT` statements (see `init.sql`)
- MongoDB roles are defined in `init-mongo.js`
- Service accounts use the **least privilege** required for their pipeline step

---

## 5. Data Retention

| Data class | Retention | Disposal method |
|---|---|---|
| Raw API logs | 90 days | hard-delete from `ingestion_audit` |
| Minute-resolution HR | 13 months | aggregate to daily, hard-delete raw |
| Daily activity | 7 years | cold storage (S3 Glacier) after 2 years |
| Lab results | per local regulation (typically 7–10 years) | encrypted archive |
| `data_quality_log` | 13 months | rolling delete |

---

## 6. Quality Standards (SLA)

The pipeline targets the following Service Level Objectives:

| Metric | Target | Alerting threshold |
|---|---|---|
| Completeness rate (required cols) | ≥ 99.0% | breach for 2 consecutive days |
| Uniqueness on primary keys | 100.0% | any duplicate triggers PagerDuty |
| Timeliness (ingestion lag) | < 6 h | > 12 h |
| Outlier rate (statistical Z > 3) | < 1.0% | > 2.0% sustained 3 days |

A failing SLA opens a Jira ticket auto-assigned to the Data Engineering
on-call rotation, with the relevant `data_quality_log` rows attached.

---

## 7. Incident Response — Root Cause Workflow

1. Quality engine flags an anomaly → row written to `data_quality_log`
2. On-call analyst opens `notebooks/02_anomaly_investigation.ipynb`
3. Trace lineage backwards: `data_quality_log` → raw record → API log
4. Categorize root cause:
   - **Device bug** → ticket to Engineering with `ingestion_audit` rows
   - **User error** → Product Manager to consider UX fix
   - **Clinical threshold drift** → Operations / Clinical Ops review
5. Document resolution in the Jira ticket and update this policy if needed

---

## 8. Cross-Functional Communication Protocol

| Audience | Deliverable | Cadence |
|---|---|---|
| **Engineering** | Data Health Dashboard, failed-check logs | Daily |
| **Product Managers** | Wellness Trends Dashboard, feature DAU/WAU | Weekly |
| **Operations / Clinical** | Threshold review, flagged outlier report | Monthly |
| **Leadership** | Executive Dashboard, DQS trend | Monthly |

---

## 9. Approval & Change Log

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0 | 2026-Q2 | Data Analyst | Initial publication |

Any modification to this policy requires sign-off from:
- Head of Engineering
- Head of Product
- Clinical Operations Lead
- Legal / Compliance
