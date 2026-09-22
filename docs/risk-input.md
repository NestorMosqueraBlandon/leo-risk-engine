# RiskInput Contract

> Version: 1.0.0 | Status: Active | Last updated: 2026-09-21

## 1. What is RiskInput?

`RiskInput` is the canonical entry contract for Leo Risk Engine. It represents **everything the engine can know about a student at a specific point in time**.

It is the stable boundary between external data producers and the internal feature pipeline:

```
External Data (SIS, LMS, ETL, files, APIs)
       ↓
   Adapter / Normalizer
       ↓
   RiskInput (canonical)
       ↓
   Feature Pipeline
       ↓
   Model
```

**`leo-risk-engine` does not depend on `leoApi`.** Any producer capable of generating a valid RiskInput can use the engine.

## 2. What is NOT RiskInput

- RiskInput is **not** a database record
- RiskInput is **not** a feature vector
- RiskInput is **not** a prediction
- RiskInput does **not** contain derived features (GPA trends, attendance rates, etc.)
- RiskInput does **not** contain PII (names, emails, phones, document numbers)
- RiskInput does **not** assume any specific SIS or country

## 3. The `as_of` Timestamp

Every RiskInput has an `as_of` timestamp that means:

> **This is the exact moment up to which information may be used to produce a prediction.**

Any observation with `available_at > as_of` is **future data** and is **rejected**.

Example:
```
as_of: 2026-09-21T12:00:00Z

grade.available_at: 2026-09-20T08:00:00Z  ← OK (available before as_of)
grade.available_at: 2026-09-22T08:00:00Z  ← REJECTED (future data)
```

## 4. `observed_at` vs `available_at`

These are different concepts:

| Field | Meaning | Example |
|---|---|---|
| `observed_at` | When the real-world event actually happened | "The student was absent on September 5" |
| `available_at` | When the system could know this data | "The university uploaded the absence on September 8" |

For preventing leakage, the relevant field is `available_at`. A grade recorded on September 5 but uploaded on September 8 cannot be used for predictions made before September 8.

**We do NOT assume `observed_at == available_at`.**

## 5. Point-in-Time Correctness

The `RiskInput` model validator enforces this rule:

> **Every observation with `DataAvailability` must satisfy `available_at <= as_of`.**

If any observation violates this, the entire `RiskInput` is rejected with a `FutureObservationError` that identifies:
- Which field/observation violated the rule
- The `available_at` timestamp
- The `as_of` timestamp

No PII is included in the error message.

## 6. Blocks

### 6.1 `academic`

Academic data observable at `as_of`:

| Field | Type | Description |
|---|---|---|
| `enrollments` | `list[Enrollment]` | Enrollment records across periods |
| `course_enrollments` | `list[CourseEnrollment]` | Course-level enrollments |
| `courses` | `list[Course]` | Course catalog entries |
| `grade_observations` | `list[GradeObservation]` | Individual grade observations |

**No derived features.** Only observed/canonical data.

### 6.2 `attendance`

| Field | Type | Description |
|---|---|---|
| `observations` | `list[AttendanceObservation]` | Individual attendance records |

Raw event-level data. The feature pipeline computes `attendance_rate_30d`, `streak`, etc.

### 6.3 `financial` (optional)

| Field | Type | Description |
|---|---|---|
| `records` | `list[FinancialStatusRecord]` | Financial status records |

**Entirely optional.** Some institutions don't track financial data or it's not relevant.

### 6.4 `engagement` (optional)

| Field | Type | Description |
|---|---|---|
| `events` | `list[EngagementEvent]` | LMS/activity events |

Raw interaction events. `response_rate`, `engagement_delta` are computed later.

### 6.5 `supports` (optional)

| Field | Type | Description |
|---|---|---|
| `records` | `list[StudentSupport]` | Support service records |

Tutoring, counseling, mentoring, etc. Whether support is "active" is a feature, not input.

### 6.6 `interventions` (optional)

| Field | Type | Description |
|---|---|---|
| `records` | `list[Intervention]` | Known interventions |

Advisor outreach, email campaigns, probation warnings, etc.

### 6.7 `institutional_context`

Context that changes the meaning of other data:

| Field | Type | Description |
|---|---|---|
| `period_id` | `str \| None` | Current period ID |
| `calendar_type` | `str` | semester, trimester, quarter, etc. |
| `program_level` | `EducationLevel \| None` | undergraduate, graduate, etc. |
| `credit_system` | `str` | semester_credits, ects, etc. |
| `periods_completed` | `int \| None` | Student's progress |
| `period_position_ratio` | `float \| None` | Position in period (0.0-1.0) |

## 7. Available Sources

The `available_sources` field explicitly tracks which data sources exist for this student:

```python
SourceAvailability(
    source_id="financial",
    status=SourceStatus.NOT_PROVIDED,  # Institution doesn't provide this
)
```

This distinguishes between:
- `AVAILABLE` — source is integrated and has data
- `NOT_PROVIDED` — source exists but the institution didn't send data
- `NOT_INTEGRATED` — source is not connected
- `EMPTY` — source is connected but has no data for this student

**Critical for missing data policy.** "No data" is not the same as "data not available."

## 8. Extensions

Country/institution-specific data goes in `extensions`:

```json
{
  "extensions": {
    "co.education": {
      "admission_exam_score": 315
    },
    "us.collegeboard": {
      "sat_score": 1200
    }
  }
}
```

Rules:
- Keys **must** be namespaced (e.g., `co.education`, `us.collegeboard`)
- Values are `dict[str, Any]` with no schema constraints
- Extensions are **optional** — the engine works without them
- Models that use extensions must handle their absence gracefully

## 9. Versioning

`schema_version` follows semantic versioning:

| Change type | Version bump | Example |
|---|---|---|
| New optional field | Minor | `1.0.0` → `1.1.0` |
| Breaking change (field removed, semantics changed) | Major | `1.0.0` → `2.0.0` |
| Documentation/correction | Patch | `1.0.0` → `1.0.1` |

## 10. PII

**RiskInput must NOT require:**
- `first_name`, `last_name`, `full_name`
- `email`, `phone`, `cell_phone`
- `document_number`, `passport`, `ssn`, `national_id`
- `address`, `username`, `photo`

The engine works with `student_id` + observations + context, not personal identity.

The `Student` contract in `contracts/core.py` has optional `date_of_birth` and `gender` fields — these are not required in RiskInput and are only used when the institution provides them for age-related features.

## 11. Canonical Serialization

`RiskInput` supports deterministic serialization for hashing:

```python
risk_input = RiskInput(...)
canonical_dict = risk_input.to_canonical_dict()
hash_value = risk_input.compute_hash()
```

The canonical dict:
- Sorts all temporal lists by `(available_at, observed_at)`
- Removes auto-generated timestamps (`created_at`, `updated_at`)
- Produces identical output for equivalent inputs regardless of insertion order

## 12. How to Build an Adapter

To connect any external system to Leo Risk Engine:

1. **Map IDs**: Convert external student/program/period IDs to opaque strings
2. **Normalize timestamps**: Convert all timestamps to timezone-aware UTC datetimes
3. **Map statuses**: Convert SIS-specific status codes to canonical enums
4. **Set `available_at`**: Determine when each record became available in the system
5. **Set `observed_at`**: Determine when each event actually happened
6. **Classify sources**: Mark each data source as AVAILABLE/NOT_PROVIDED/NOT_INTEGRATED/EMPTY
7. **Add extensions** (optional): Map country-specific data to namespaced extensions
8. **Validate**: Construct `RiskInput` and let Pydantic validate point-in-time correctness

Example adapter pseudocode:
```python
def adapt_sis_record(sis_record, as_of: datetime) -> RiskInput:
    return RiskInput(
        student_id=sis_record["student_id"],
        institution_id=institution_id,
        as_of=as_of,
        academic=AcademicBlock(
            enrollments=[adapt_enrollment(e) for e in sis_record["enrollments"]],
            ...
        ),
        ...
    )
```

## 13. OpenAPI

When `LEO_DEBUG=true`, the `RiskInput` schema appears in the OpenAPI docs at `/docs` via the internal validation endpoint `POST /internal/validate-risk-input`.

This endpoint is for development/testing only and does NOT perform inference.
