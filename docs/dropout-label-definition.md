# Dropout Label Definition

> Version: 1.0.0 | Status: Active | Last updated: 2026-09-21

## 1. Purpose

This document formally defines what "dropout" means in Leo Risk Engine v2. It establishes the rules for assigning outcome labels to student enrollment records, the data requirements for each label, and the handling of edge cases across different academic calendar systems worldwide.

The label definition is **not** a statistical assumption — it is a **contract** between data providers, the ML pipeline, and downstream consumers (advisors, dashboards, automated interventions).

## 2. Core Definition

**Dropout** is defined as:

> A student who was enrolled in academic period **T** (reference period) and is **not enrolled** in period **T+1** (observation period) **after T+1 has been officially closed/certified** by the institution, **and** the student did not complete the program through any recognized non-dropout exit path.

### What is NOT dropout

- The student graduated (`GRADUATED`)
- The student died (`DECEASED`)
- The student is still enrolled in T+1 (`CONTINUED`)
- T+1 has not yet closed — we cannot determine the outcome (`PENDING`)
- Data is incomplete or contradictory (`UNKNOWN`)

## 3. Outcome Statuses

| Status | Meaning | Can assign? |
|---|---|---|
| `CONTINUED` | Enrolled in T, enrolled in T+1 after T+1 closed | Yes, after T+1 closes |
| `DROPPED_OUT` | Enrolled in T, not enrolled in T+1 after T+1 closed, no recognized exit path | Yes, after T+1 closes |
| `PENDING` | T+1 has not yet been officially closed | No — wait for closure |
| `UNKNOWN` | Data is incomplete, missing, or contradictory | No — request better data |

### 3.1 CONTINUED

The student was enrolled in period T and is enrolled in period T+1, confirmed after T+1 has been officially closed by the institution.

**Requirements:**
- Enrollment record in T
- Enrollment record in T+1
- T+1 must be closed/certified
- Both records must reference the same student and program

**Censorship type:** `RIGHT_CENSORED` — we observe that the student did NOT drop out by the end of T+1, but we don't know what happens after.

### 3.2 DROPPED_OUT

The student was enrolled in period T and is NOT enrolled in period T+1, after T+1 has been officially closed, and the student did not exit through a recognized non-dropout path.

**Requirements:**
- Enrollment record in T
- No enrollment record in T+1 (or explicit withdrawal)
- T+1 must be closed/certified
- An exit reason must be provided (may be `NOT_REPORTED`)
- The exit reason must not be a non-dropout reason (`GRADUATED`, `DECEASED`, or `NONE`)

**Censorship type:** `OBSERVED` — we know the dropout event occurred. For survival analysis, we know the exact period when the student dropped out.

### 3.3 PENDING

Period T+1 has not yet been officially closed by the institution. We cannot determine whether the student continued or dropped out until the institution certifies the period.

**When this occurs:**
- Current academic period is in progress
- Data was pulled before the period closed
- Institution has not yet submitted final enrollment data

**Censorship type:** `NOT_CENSORABLE` — this record cannot be used for model training or evaluation until the period closes.

**Important:** PENDING records should NOT be imputed as either CONTINUED or DROPPED_OUT. They must be re-evaluated after period closure.

### 3.4 UNKNOWN

Data is incomplete, missing, or contradictory. We cannot reliably determine the student's enrollment status.

**When this occurs:**
- No enrollment record found for either T or T+1
- Conflicting records (e.g., student marked as both enrolled and withdrawn)
- Institution data is incomplete or not yet loaded
- Student record cannot be matched across periods

**Censorship type:** `NOT_CENSORABLE` — this record cannot be used for model training or evaluation.

**Important:** UNKNOWN records should trigger a data quality investigation, not be silently dropped or imputed.

## 4. Exit Reasons

When a student is classified as `DROPPED_OUT`, we track the exit reason to distinguish between different types of departure.

| Reason | Counts as dropout? | Description |
|---|---|---|
| `NONE` | No | Student did not leave (used with CONTINUED) |
| `GRADUATED` | No (default) | Completed program requirements |
| `TRANSFERRED` | No (default) | Moved to another institution |
| `AUTHORIZED_LEAVE` | No (default) | Official leave of absence (medical, military, personal) |
| `VOLUNTARY_WITHDRAWAL` | **Yes** | Chose to leave without completing |
| `ACADEMIC_DISMISSMENT` | **Yes** | Removed for academic performance |
| `ADMINISTRATIVE` | **Yes** | Non-academic removal (disciplinary, financial) |
| `NOT_REPORTED` | **Yes** | No reason provided |
| `DECEASED` | No | Student passed away |

### 4.1 Configurable exit path treatment

The `LabelContract` allows configuring which exit paths count as dropout:

- `treat_graduation_as_dropout` — default `False`. Set to `True` if graduation is considered a form of "leaving" for specific analyses.
- `treat_transfer_as_dropout` — default `False`. Some institutions consider transfers as dropouts.
- `treat_authorized_leave_as_dropout` — default `False`. Authorized leave is temporary; the student may return.

### 4.2 Exit reason normalization

Data from different institutions uses different terminology. The `LabelContract.resolve_exit_reason()` method normalizes raw strings to canonical `ExitReason` values. Examples:

| Raw input | Resolved to |
|---|---|
| `graduado`, `graduated`, `egresado`, `completed` | `GRADUATED` |
| `transferencia`, `traslado`, `transferred` | `TRANSFERRED` |
| `permiso`, `suspension`, `pausa autorizada` | `AUTHORIZED_LEAVE` |
| `retiro_voluntario`, `withdrawal`, `renuncia` | `VOLUNTARY_WITHDRAWAL` |
| `cancelacion_academica`, `academic_dismissal` | `ACADEMIC_DISMISSMENT` |
| `administrativo`, `disciplinario`, `financiero` | `ADMINISTRATIVE` |
| `fallecido`, `deceased` | `DECEASED` |
| Any unrecognized string | `NOT_REPORTED` |
| `None` (missing) | `NOT_REPORTED` |

## 5. Censorship for Survival Analysis

Survival analysis requires distinguishing between observed events and censored observations. The `CensorshipType` enum maps directly to survival analysis concepts.

| Type | Meaning | Used in training? |
|---|---|---|
| `OBSERVED` | Dropout event was observed in a specific period | Yes — event time is known |
| `RIGHT_CENSORED` | Student was still enrolled at end of observation | Yes — event hasn't happened yet |
| `LEFT_CENSORED` | Student had already dropped out before observation began | Yes — but less precise |
| `INTERVAL_CENSORED` | Dropout occurred within a known time interval | Yes — interval is the event window |
| `NOT_CENSORABLE` | Record cannot be used for survival analysis | **No** — PENDING or UNKNOWN |

### 5.1 Censorship assignment rules

| Outcome Status | Censorship Type |
|---|---|
| `CONTINUED` | `RIGHT_CENSORED` |
| `DROPPED_OUT` | `OBSERVED`, `LEFT_CENSORED`, or `INTERVAL_CENSORED` |
| `PENDING` | `NOT_CENSORABLE` |
| `UNKNOWN` | `NOT_CENSORABLE` |

### 5.2 Why RIGHT_CENSORED for CONTINUED?

When a student continues from T to T+1, we know they didn't drop out **by the end of T+1**. But we don't know what happens in T+2, T+3, etc. In survival analysis terms: the student is "at risk" but the event hasn't occurred yet within our observation window. This is classic right censoring.

## 6. Academic Calendar Support

Leo Risk Engine supports multiple academic calendar systems. The calendar type affects:

1. **Period naming** — semesters use "2024-1", "2024-2"; trimesters use "2024-T1", "2024-T2", "2024-T3"
2. **Survival time computation** — converting periods to months requires knowing the calendar
3. **Period closure timing** — different calendars close at different times of year

### 6.1 Supported calendar types

| Calendar | Periods/year | Example systems |
|---|---|---|
| `SEMESTER` | 2 | US, Europe, most of Asia |
| `TRIMESTER` | 3 | Some European countries, parts of Latin America |
| `QUARTER` | 4 | US community colleges |
| `QUADRIMESTER` | 3 (4 months each) | Colombia (Feb-May, Jun-Aug, Sep-Dec) |
| `ANNUAL` | 1 | Some professional programs |
| `CUSTOM` | Varies | Institution-specific |

### 6.2 Period-to-month mapping

For survival analysis, periods must be convertible to time durations. The mapping depends on the calendar type and the institution's specific schedule. This mapping should be provided by the institution or configured in the `LabelContract`.

## 7. Edge Cases

### 7.1 Graduation

Graduation is **not** dropout by default. A student who completes their program is a success story, not a risk event. The `LabelContract` provides a `treat_graduation_as_dropout` flag for institutions that need different behavior.

**When a student graduates:** `OutcomeStatus.DROPPED_OUT` with `exit_reason=GRADUATED` is **not allowed** by default. The entity validation rejects this combination. If graduation should count as dropout, set `treat_graduation_as_dropout=True` in the contract.

### 7.2 Transfer

Transfer is **not** dropout by default. A student who transfers to another institution may be continuing their education elsewhere. However, from the perspective of the originating institution, they are no longer enrolled.

**Default behavior:** Transfer → `DROPPED_OUT` with `exit_reason=TRANSFERRED` is allowed but `is_dropout_exit()` returns `False` by default. The institution can configure `treat_transfer_as_dropout=True`.

### 7.3 Authorized Leave

Authorized leave (medical, military, personal) is **not** dropout. The student intends to return. However, if they don't return after the leave period, they should be reclassified.

**Default behavior:** Authorized leave → `DROPPED_OUT` with `exit_reason=AUTHORIZED_LEAVE` is allowed but `is_dropout_exit()` returns `False` by default.

### 7.4 Incomplete Data

When data is missing:
1. **Missing enrollment record for T+1** — Could mean dropout OR could mean data hasn't been loaded yet. Default to `UNKNOWN`, not `DROPPED_OUT`.
2. **Missing enrollment record for T** — Cannot determine if student was enrolled. Default to `UNKNOWN`.
3. **Conflicting records** — Student marked as both enrolled and withdrawn. Default to `UNKNOWN`.

**Never impute dropout from missing data.** Missing data must be resolved through data quality checks, not statistical assumptions.

### 7.5 Period Not Closed

If the observation period (T+1) has not been officially closed:
- Status must be `PENDING`
- Censorship type must be `NOT_CENSORABLE`
- The record cannot be used for training or evaluation

**This is the most common source of false dropouts.** Data pulled mid-period shows "no enrollment" because records haven't been updated, not because the student left.

### 7.6 Gap Periods

A student may skip a period (e.g., enrolled in T, not in T+1, enrolled again in T+2). This is handled via:
- `periods_elapsed` field — can be greater than 1
- `AUTHORIZED_LEAVE` exit reason — if the gap was planned
- The `is_dropout` flag should only be set if the student does NOT return

### 7.7 Multiple Programs

A student enrolled in multiple programs simultaneously should be tracked per-program. Dropout in one program does not necessarily mean dropout from the institution.

## 8. Data Requirements

### 8.1 Minimum data for label assignment

To assign `CONTINUED` or `DROPPED_OUT`, the following data is required:

| Field | Required | Description |
|---|---|---|
| Student ID | Yes | Unique identifier, consistent across periods |
| Institution ID | Yes | Unique institution identifier |
| Program ID | Yes | Academic program identifier |
| Reference period (T) | Yes | Period where student was enrolled |
| Observation period (T+1) | Yes | Period to check for continuation |
| Enrollment record T | Yes | Proof of enrollment in T |
| Enrollment record T+1 | Yes | Proof of enrollment (or lack thereof) in T+1 |
| Period closure date | Yes | Official closure date for T+1 |
| Exit reason | Recommended | Why the student left (if applicable) |
| Calendar type | Yes | Academic calendar structure |

### 8.2 What institutions must provide

1. **Enrollment records** for each period, with consistent student IDs
2. **Period closure dates** — official dates when each period is certified
3. **Exit reasons** — standardized reason codes for students who leave
4. **Calendar type** — which academic calendar the institution uses
5. **Program information** — program ID, name, duration

### 8.3 Data quality expectations

- Student IDs must be consistent across periods (no re-assignment)
- Period codes must follow a consistent format
- Enrollment records should have timestamps
- Exit reasons should use standardized codes (or the `LabelContract` normalization will handle variations)

## 9. Label Versioning

The label definition is versioned using semantic versioning (`MAJOR.MINOR.PATCH`):

- **MAJOR** — Breaking changes to the label definition (e.g., changing what counts as dropout)
- **MINOR** — New exit reasons, new calendar types, new validation rules
- **PATCH** — Documentation corrections, normalization additions

Every change to the label rules must be tracked with a new version. This ensures:

1. **Reproducibility** — Models trained with v1.0.0 labels can be compared to models trained with v1.1.0 labels
2. **Auditability** — We can trace which label definition was used for any prediction
3. **Backward compatibility** — Old models can still be served, but their labels may differ from current definitions

## 10. Implementation Reference

### 10.1 Source files

| File | Contents |
|---|---|
| `src/leo_risk/domain/enums.py` | `OutcomeStatus` enum |
| `src/leo_risk/domain/exit_reason.py` | `ExitReason` enum + frozensets |
| `src/leo_risk/domain/censorship.py` | `CensorshipType` enum |
| `src/leo_risk/domain/academic_calendar.py` | `AcademicCalendar` enum |
| `src/leo_risk/domain/entities/student_outcome.py` | `StudentOutcome` entity |
| `src/leo_risk/domain/label_contract.py` | `LabelContract` + `LabelRule` |
| `src/leo_risk/domain/label_version.py` | `LabelVersion` value object |

### 10.2 Validation rules (enforced by entity)

1. `CONTINUED` requires `exit_reason=NONE`
2. `DROPPED_OUT` requires a specific exit reason (not `NONE`)
3. `DROPPED_OUT` cannot have `exit_reason` in `NON_DROPOUT_REASONS` (`GRADUATED`, `DECEASED`, `NONE`)
4. `PENDING` and `UNKNOWN` can only have `exit_reason` in `{NONE, NOT_REPORTED}`
5. `DROPPED_OUT` cannot be `RIGHT_CENSORED`
6. `CONTINUED` cannot be `OBSERVED`
7. `PENDING` and `UNKNOWN` must have `censorship_type=NOT_CENSORABLE`
8. `reference_period` and `observation_period` must be different
9. `student_id`, `institution_id`, `program_id` must be non-empty
10. `confidence_score` must be in [0.0, 1.0]
11. `periods_elapsed` must be >= 0

### 10.3 Tests

All validation rules are covered by unit tests in `tests/unit/test_student_outcome.py`. The test suite includes:

- Happy paths for all four outcome statuses
- Validation failures for invalid status/reason/censorship combinations
- Label version bumping
- Label contract exit reason resolution
- Edge cases (unicode, zero confidence, custom calendars)
