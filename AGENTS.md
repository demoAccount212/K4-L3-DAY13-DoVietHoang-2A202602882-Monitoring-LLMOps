# AGENTS.md - K4-L3B Day 13 Monitoring & LLMOps

> Compact instruction file for OpenCode sessions. Every line answers: "Would an agent likely miss this without help?"

## Setup Commands (run from repo root)

**Create venv and install deps:**

Windows PowerShell:
```powershell
python -m venv .venv
\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS/Linux:
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

**Start the API:**
```bash
uvicorn app.main:app --reload --env-file .env
```

**Run all verifications:**
```bash
python -m pytest -q
python scripts/validate_logs.py
python scripts/validate_dashboard.py
```

## Critical TODOs (code has missing implementation)

These are the most important — an agent will likely miss them without help:

- **`app/middleware.py`**: CorrelationIdMiddleware has 4 TODOs:
  1. Clear contextvars to avoid leakage between requests (`clear_contextvars()`)
  2. Extract `x-request-id` from headers or generate new one in format `req-<8-char-hex>`
  3. Bind correlation_id to structlog contextvars (`bind_contextvars(correlation_id=correlation_id)`)
  4. Add correlation_id and processing time to response headers

- **`app/main.py` line 51-52**: Enrich logs with request context — uncomment and add `bind_contextvars(...)` with `user_id_hash`, `session_id`, `feature`, `model`, `env`

- **`app/logging_config.py` line 45-46**: PII scrubbing processor is commented out — uncomment `scrub_event` in the processors list

- **`app/pii.py` line 11**: TODO — add more patterns (e.g., Passport, Vietnamese address keywords)

## Correlation ID Flow (critical for tracing)

- `correlation_id` travels from `CorrelationIdMiddleware` → `request.state.correlation_id` → structured logs via `structlog` contextvars → Langfuse trace metadata
- Without binding to contextvars, correlation_id is lost between requests (major blocker)
- Validate: `validate_logs.py` checks that `correlation_id` is NOT `"MISSING"` for `service == "api"` records

## PII Scrubbing

- `app/pii.py` defines patterns: `email`, `phone_vn`, `cccd`, `credit_card`
- `scrub_text()` replaces matches with `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, etc.
- `app/logging_config.py` has `scrub_event()` processor that runs `scrub_text` on payload fields and event name
- **Validate**: `validate_logs.py` detects raw PII in logs even after scrubbing — score drops 30 pts if found
- Structured log schema requires: `ts`, `level`, `service`, `event`, `correlation_id` + enrichment: `user_id_hash`, `session_id`, `feature`, `model`

## Langfuse Tracing

- App uses `langfuse==4.15.6` Python SDK
- Set `.env` with: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, `LANGFUSE_PROMPT_NAME=day13-chat`, `LANGFUSE_PROMPT_LABEL=production`
- `tracing_enabled()` checks both keys exist
- Traces have root observation `lab-agent-run` with child observations for `retrieval` and `generation`
- **Prompt versioning**: `resolve_prompt()` uses `LANGFUSE_PROMPT_NAME` and `LANGFUSE_PROMPT_LABEL` — promote/rollback `production` label between prompt versions
- Evidence: 10+ traces in personal project `day13-k4-l3b-<MSSV>`, trace waterfall with root/retrieval/generation, prompt v1/v2 with promote/rollback

## Dashboard Config (`config/dashboard.yaml`)

- Must have exactly 6 panels with IDs: `latency`, `traffic`, `errors`, `cost`, `tokens`, `quality`
- Each panel needs: `title`, `source`, `events`, `fields`, `aggregations`, `query`, `unit`, `threshold`
- `schema_version` must be `1`, `time_range_minutes` must be `60`, `refresh_seconds` must be `15–30`
- Validate: `scripts/validate_dashboard.py` returns exit code 1 if any check fails

## SLO & Error Budget (`config/slo.yaml`)

- Primary SLO: `99.5%` latency P95 ≤ 3000ms in 28-day window
- Error budget: `0.5%` — means max 50 failed/slow requests per 10,000
- Guardrails: `error_rate_pct_max: 2`, `daily_cost_usd_max: 2.5`, `quality_score_avg_min: 0.75`, `retrieval_success_rate_pct_min: 90`

## Alert Rules (`config/alert_rules.yaml`)

- 3 alerts, symptom-based, with: `severity`, `duration`, `owner`, `Slack channel`, `runbook`
- Currently all have `TODO_` prefixes — fill in based on these:
  1. **HighLatencyP95**: p95(latency_ms) > 3000ms for 5m → severity: high, owner: student-<MSSV>
  2. **ErrorRateHigh**: error_rate > 2% for 5m → severity: critical, owner: student-<MSSV>
  3. **CostSpike**: daily_cost_usd > 2.5 → severity: medium, owner: student-<MSSV>
- See `docs/alerts.md` for template

## Challenge Incident (CP3 only)

- `config/challenge.json` is sent by Lab Coach, **do not commit/push/share**
- Inject via: `python scripts/inject_incident.py` (or with `--scenario` for practice)
- Investigation chain: **Metrics → Logs → Traces → Root cause**
  1. Check dashboard for metric anomaly + time range
  2. Filter `data/logs.jsonl` for abnormal `correlation_id`
  3. Find trace with same `correlation_id`, identify problematic span
  4. Write root cause, fix action, preventive measure into `submission/REPORT.md`

## Evidence Checklist (for `submission/REPORT.md`)

All 14 files must be in `submission/evidence/` with relative paths:

```
01-pytest.png, 02-log-validator.png, 03-dashboard-validator.png,
04-structured-log.png, 05-pii-redaction.png, 06-trace-list.png,
07-trace-waterfall.png, 08-trace-metadata.png, 09-prompt-versions.png,
10-prompt-rollback.png, 11-dashboard-overview.png, 12-incident-metric.png,
13-incident-log.png, 14-incident-trace.png
```

- `04`, `05`, `13` from terminal/`data/logs.jsonl`
- `06–10`, `14` from personal Langfuse project `day13-k4-l3b-<MSSV>`
- All paths must be relative and openable on GitHub
- No API keys, secrets, or raw PII in any evidence

## Key Mnemonics

- **Metrics → Logs → Traces → Root cause** — investigation chain
- **correlation_id** — ties together metrics, logs, and traces for one request
- **SLO 99.5% = error budget 0.5%** — max 50 bad requests per 10,000
- **Prompt v1/v2 + production label** — promote/rollback for safe updates