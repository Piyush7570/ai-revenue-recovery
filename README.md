# PayRevive — AI Revenue Recovery

> This project was built for **Track 03: AI Revenue Recovery** of the Razorpay Buildathon 2026.

PayRevive is an intelligent, closed-loop payment-failure recovery system. It diagnoses why a payment failed, validates a recovery strategy through a hard-coded safety policy engine, and then executes the safest possible action — all without requiring a live LLM key. An optional Gemini integration upgrades the rule engine to live AI reasoning when configured.

---

## Overview

Merchants lose significant revenue to failed one-time payments, recurring subscription charges, and checkout abandonments. PayRevive provides an automated recovery pipeline that:

- Ingests payment-failure events (real Razorpay webhooks or simulation)
- Diagnoses the root cause using a rule-based engine (or live Gemini AI)
- Selects and validates a recovery strategy via a deterministic safety policy engine
- Executes the action (retry, payment link, notification, or escalation)
- Cancels pending retries the moment a webhook confirms payment success
- Maintains a full, immutable audit trail per case

All of the above works **fully offline** — no external API keys are required to run, evaluate, or demo the system.

---

## Problem

Traditional retry logic is context-blind:

| Root Cause | Blind-Retry Result |
|---|---|
| `EXPIRED_CARD` | Guaranteed to fail again; incurs gateway fee each attempt |
| `INSUFFICIENT_FUNDS` | Fails repeatedly; damages customer relationship |
| `CHECKOUT_ABANDONED` | No card token exists; retry is not even possible |
| `GATEWAY_TIMEOUT` | Actually needs an immediate retry — delay hurts conversion |

Context-blind systems also lack protection against duplicate retries, race conditions, and customer opt-outs, leading to compounding costs and poor customer experience.

---

## Solution

PayRevive implements an **"AI Proposes → Deterministic Engine Executes"** architecture:

1. **Failure Ingestion**: A Razorpay-format webhook payload arrives at `POST /api/webhooks/razorpay`.
2. **Diagnosis**: The AI layer maps the failure code to a root-cause enum.
3. **Strategy Selection**: The AI recommends a recovery action and delay window.
4. **Policy Validation**: A hard-coded `PolicyEngine` independently re-validates the proposal.
5. **Execution**: If approved, the `ActionExecutor` calls the payment provider.
6. **Webhook Closure**: A `payment.captured` webhook atomically closes the case and cancels all pending retries.

---

## Why PayRevive

- **Zero unnecessary card retries** on expired cards or checkout abandonments
- **Race-condition safe**: payment success webhook always wins over any queued retry
- **Idempotent**: duplicate webhooks are detected and dropped using the Razorpay event ID
- **Customer-friendly**: hard limits on notification frequency and opt-out support
- **Runs fully offline**: the deterministic fallback requires no external services

---

## How It Works

```
Webhook / Simulator
      │
      ▼
 WebhookService           ← idempotency check, state initialisation
      │
      ▼
  LLMService              ← diagnosis + strategy (Gemini API or rule-based fallback)
      │
      ▼
 PolicyEngine             ← deterministic hard-coded safety rules
      │
      ▼
 ActionExecutor           ← retry card / create payment link / send notification
      │
      ▼
 SimulationProvider       ← mock Razorpay API (or RazorpayProvider if keys set)
      │
      ▼
 StateMachine + AuditService  ← state transition + immutable audit log
      │
      ▼
 InMemoryScheduler        ← background thread fires delayed actions
```

---

## Architecture

```
ai-revenue-recovery/
├── backend/                     # Python FastAPI service
│   ├── app/
│   │   ├── main.py              # FastAPI app, all REST endpoints, seed data
│   │   ├── config.py            # Pydantic-settings (reads .env)
│   │   ├── database.py          # SQLAlchemy engine + session factory
│   │   ├── models.py            # ORM models (Customer, Payment, RecoveryCase …)
│   │   ├── schemas.py           # Pydantic request/response schemas + enums
│   │   ├── state_machine.py     # Enforces valid state transitions
│   │   ├── policy_engine.py     # Deterministic safety rules
│   │   ├── action_executor.py   # Executes approved recovery actions
│   │   ├── scheduler.py         # Background thread scheduler
│   │   ├── ai/
│   │   │   └── service.py       # LLMService (Gemini + rule-based fallback)
│   │   ├── providers/
│   │   │   ├── base.py          # BasePaymentProvider ABC
│   │   │   ├── razorpay.py      # Live Razorpay REST client
│   │   │   └── simulation.py    # Mock provider (default)
│   │   └── services/
│   │       ├── webhook.py       # WebhookService — event processing
│   │       ├── audit.py         # AuditService — event logging
│   │       └── evaluation.py    # EvaluationEngine — 50-case benchmark
│   ├── tests/
│   │   └── test_recovery.py     # 8 pytest tests
│   ├── run.py                   # uvicorn entry point
│   └── requirements.txt
└── frontend/                    # React + Vite + TypeScript dashboard
    └── src/
        └── App.tsx              # Single-file merchant dashboard UI
```

---

## Recovery Strategies

The AI layer (or fallback) maps each failure class to a strategy:

| Failure Class | Strategy | Reasoning |
|---|---|---|
| `INSUFFICIENT_FUNDS` | Create Payment Link (24 h delay) | Card is active but empty; link lets customer pay from any method |
| `EXPIRED_PAYMENT_METHOD` | Create Payment Link (1 h delay) | Card is dead; retrying is pointless — customer must provide a new card |
| `TRANSIENT_GATEWAY_ERROR` | Retry Payment (0 h, immediate) | Transient failure; immediate retry has highest success probability |
| `LIMIT_EXCEEDED` | Create Payment Link (24 h delay) | Limit resets after cycle; link provides an alternative payment method |
| `CUSTOMER_FRICTION` | Create Payment Link (2 h delay) | OTP / 3DS failure; link gives customer a fresh authentication attempt |
| `CHECKOUT_ABANDONMENT` | Send Notification (4 h delay) | No card token; recovery relies on re-engagement notification |
| `UNKNOWN` | Create Payment Link (12 h delay) | Conservative fallback covering unclassified codes |

---

## Safety & Guardrails

`PolicyEngine.validate_action()` enforces the following rules in order, **completely independent of the AI layer**. Any violation returns `(False, reason)` and blocks execution:

1. **Terminal-state check** — no action on cases already recovered, cancelled, disputed, etc.
2. **Duplicate payment check** — blocks retry if the payment has already been captured
3. **Customer opt-out** — hard block on any communication after opt-out keyword detected
4. **Dispute flag** — all actions blocked while a dispute is open
5. **Max-retry limit** — default 3 attempts; configurable via `MAX_RETRIES` env var
6. **Idempotency** — action record checked for `success` or `executing` status before re-run
7. **Notification spacing** — minimum 12 h between notifications; max 3 per case

---

## Simulation & Showcase Scenarios

All scenarios are triggered via `POST /api/simulation/showcase/{scenario_name}`:

| Scenario | Trigger | What It Demonstrates |
|---|---|---|
| `insufficient_funds` | `INSUFFICIENT_FUNDS` failure code | Payment-link strategy with 24 h delay |
| `gateway_error` | `GATEWAY_ERROR` failure code | Immediate card retry on transient failure |
| `card_expired` | `CARD_EXPIRED` failure code | Payment-link strategy; retry is never attempted |
| `checkout_abandonment` | `CHECKOUT_ABANDONED` failure code | Re-engagement notification (no card token) |
| `provider_outage` | Simulated API exception | Graceful failure: action marked failed, case kept active for fallback |
| `race_condition` | Captured webhook arriving while retry is scheduled | Scheduled retry cancelled atomically; case closes cleanly |

Additional simulation controls (toggled via `POST /api/simulation/config`):

- `outage_enabled` — forces the simulation provider to raise an exception
- `duplicate_webhook_enabled` — re-fires the same webhook to test idempotency
- `notification_failure_enabled` — forces notification delivery to fail

---

## AI Performance Evaluation

The evaluation suite runs automatically via `POST /api/evaluation/run` (or the dashboard Evaluation tab). It compares two algorithms over a **fixed 50-case synthetic dataset** using `random.seed(42)` for reproducibility.

### Important Disclosure — Offline Mode

> **The default evaluation runs in OFFLINE MODE using the deterministic rule-based fallback.**  
> No LLM API key is required to run or evaluate the system. In offline mode, the AI layer is the `get_diagnosis_fallback` / `get_action_fallback` methods in `LLMService`, which perform keyword-based mapping of failure codes to diagnosis enums. The reported 100% diagnosis and action accuracy reflects the accuracy of this deterministic fallback against the dataset's expected labels — **not real-world LLM generalisation**.  
>
> To enable **Live LLM Mode** (Gemini 1.5 Flash), set `LLM_API_KEY` in `backend/.env`. The evaluation will then call the Gemini API for each of the 50 cases and re-score accuracy live.

### Dataset

50 synthetic payment-failure cases covering 6 failure classes:

| Class | Cases | Notes |
|---|---|---|
| Insufficient Funds | 13 | Codes: `INSUFFICIENT_FUNDS`, `INSUFFICIENT_BALANCE`, `LOW_BALANCE`, `BAD_BALANCE` |
| Transient Gateway Error | 10 | Codes: `GATEWAY_TIMEOUT`, `ACQUIRER_DOWN`, `GATEWAY_ERROR`, `NETWORK_FAILURE` |
| Expired Card | 8 | Codes: `CARD_EXPIRED`, `EXPIRED_CARD` |
| Limit Exceeded | 5 | Codes: `LIMIT_EXCEEDED`, `CARD_LIMIT_REACHED`, `TXN_LIMIT_EXCEEDED` |
| Checkout Abandonment | 7 | Codes: `CHECKOUT_ABANDONED`, `ABANDONED_CHECKOUT` |
| Unknown | 7 | Codes: `UNKNOWN_ERROR`, `DO_NOT_HONOR`, `BLOCKED`, etc. |

Ground truth labels (`expected_diagnosis`, `expected_action`) are defined in the dataset and are **only compared after** the decision function returns — they are never passed in as inputs.

### Results (Offline / Deterministic Fallback Mode)

| Metric | Traditional Baseline | AI Recovery Engine | Δ |
|---|---|---|---|
| Recovered Revenue (INR) | ₹45,262 | ₹120,400 | +166% |
| Recovery Rate (Amount) | 15.9% | 42.2% | +165% |
| Recovered Cases | 17 / 50 | 34 / 50 | +100% |
| Recovery Attempt Overhead | 5.88 | 1.50 | −74% |
| Avg. Attempts per Case | 2.00 | 1.02 | −49% |
| Unnecessary Retry Rate | 24.0% | 0.0% | −100% |
| Operational Recovery Cost | ₹5,000 | ₹705 | −85% |
| False-Positive Cost | ₹4,950 | ₹0 | −100% |
| Avg. Time to Recovery | 31.1 hrs | 14.4 hrs | −54% |
| Diagnosis Accuracy | 0.0% | 100.0% | — |
| Action Selection Accuracy | 0.0% | 100.0% | — |

> **Note**: These figures are computed over the synthetic dataset with `random.seed(42)` for reproducibility. They should not be extrapolated to production traffic. Accuracy figures reflect the deterministic fallback, not a live LLM.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.10+, FastAPI, Uvicorn |
| Database | SQLite (via SQLAlchemy 2.x) |
| Background Jobs | Python threading (`InMemoryScheduler`) |
| AI / LLM | Google Gemini 1.5 Flash (optional; httpx REST) |
| Fallback Engine | Pure Python keyword-mapping (no API needed) |
| Payment Provider | Razorpay REST API (optional) / `SimulationProvider` (default) |
| Frontend | React 19, TypeScript, Vite 8, TailwindCSS v4 |
| Charts | Recharts |
| Icons | Lucide React |
| Testing | pytest 8 |

---

## Project Structure

```
ai-revenue-recovery/
├── .env.example                 ← copy to backend/.env, fill in keys
├── .gitignore
├── README.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── state_machine.py
│   │   ├── policy_engine.py
│   │   ├── action_executor.py
│   │   ├── scheduler.py
│   │   ├── ai/
│   │   │   ├── __init__.py
│   │   │   └── service.py
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── razorpay.py
│   │   │   └── simulation.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── audit.py
│   │       ├── evaluation.py
│   │       └── webhook.py
│   ├── tests/
│   │   └── test_recovery.py
│   ├── run.py
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── package.json
    ├── tailwind.config.js
    ├── vite.config.ts
    ├── tsconfig.json
    └── src/
        ├── main.tsx
        ├── App.tsx
        └── index.css
```

---

## Local Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Piyush7570/ai-revenue-recovery.git
cd ai-revenue-recovery
```

### 2. Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (all keys are optional for offline mode)
cp ../.env.example .env
# Edit .env if you want live Razorpay or Gemini integration

# Start the FastAPI server
python run.py
```

Backend available at **http://127.0.0.1:8000**  
Interactive API docs at **http://127.0.0.1:8000/docs**

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at **http://localhost:5173**

> The backend must be running before the frontend can fetch data.

---

## Environment Variables

All variables live in `backend/.env`. Copy `.env.example` as a starting point.

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./revenue_recovery.db` | SQLAlchemy connection string |
| `RAZORPAY_KEY_ID` | _(blank)_ | Razorpay API key ID. Leave blank → simulation mode |
| `RAZORPAY_KEY_SECRET` | _(blank)_ | Razorpay API key secret. Leave blank → simulation mode |
| `RAZORPAY_WEBHOOK_SECRET` | _(blank)_ | Razorpay webhook HMAC secret for signature verification |
| `LLM_API_KEY` | _(blank)_ | Google Gemini API key. Leave blank → deterministic fallback |
| `MAX_RETRIES` | `3` | Maximum payment retry attempts per case |
| `MIN_HOURS_BETWEEN_NOTIFICATIONS` | `12` | Minimum hours between customer notifications |
| `MAX_NOTIFICATIONS_PER_CASE` | `3` | Maximum notifications per recovery case |
| `HOST` | `0.0.0.0` | Uvicorn bind host |
| `PORT` | `8000` | Uvicorn bind port |

> **Offline mode (default)**: Leave `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `LLM_API_KEY` blank. The system will use `SimulationProvider` for payment operations and the rule-based fallback for AI decisions. No external services are called.

---

## API Endpoints

All endpoints are documented interactively at `http://127.0.0.1:8000/docs`.

### Dashboard

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/dashboard/summary` | Revenue at risk, recovered, active cases, distributions |

### Recovery Cases

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/recovery-cases` | List all cases (filter: `state`, `failure_reason`) |
| `GET` | `/api/recovery-cases/{case_id}` | Case detail including audit trail and actions |
| `POST` | `/api/recovery-cases/{case_id}/run` | Trigger AI diagnosis + recovery execution |
| `POST` | `/api/recovery-cases/{case_id}/approve` | Immediately execute next scheduled action |
| `POST` | `/api/recovery-cases/{case_id}/cancel` | Cancel an active case |
| `POST` | `/api/recovery-cases/{case_id}/reply` | Simulate a customer text reply (opt-out / dispute / promise-to-pay) |

### Webhooks

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/webhooks/razorpay` | Ingest Razorpay webhook payload (HMAC verified in live mode) |

### Simulation

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/simulation/config` | Get current simulation flags |
| `POST` | `/api/simulation/config` | Toggle outage / duplicate / notification-failure flags |
| `POST` | `/api/simulation/payment-failure` | Inject a new failed payment event |
| `POST` | `/api/simulation/payment-success` | Simulate a customer paying (triggers recovery webhook) |
| `POST` | `/api/simulation/showcase/{scenario}` | Trigger a named demo scenario |

Available `scenario` values: `insufficient_funds`, `gateway_error`, `card_expired`, `checkout_abandonment`, `provider_outage`, `race_condition`.

### Evaluation

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/evaluation/run` | Run 50-case benchmark and return results |
| `GET` | `/api/evaluation/results` | Same as above (GET variant for dashboard polling) |

---

## Testing

```bash
cd backend
venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS / Linux

pytest tests/ -v
```

### Test Coverage

| Test | What It Validates |
|---|---|
| `test_state_machine_transitions` | Valid and invalid state transitions including rejection of illegal transitions |
| `test_policy_engine_max_attempts` | Policy blocks retry when attempt count equals max |
| `test_policy_engine_customer_opt_out` | Policy blocks all actions after customer opt-out |
| `test_webhook_idempotency` | Duplicate webhook event is ignored; case not double-processed |
| `test_race_condition_retry_cancellation` | Captured webhook cancels queued retries atomically |
| `test_ai_fallback_diagnoses` | Rule-based fallback maps failure codes to correct diagnosis enums |
| `test_evaluation_reproducible_math` | Evaluation produces deterministic, reproducible metrics across runs |
| `test_race_condition_policy_rejection` | Policy engine blocks any action on a captured / recovered payment |

**Latest run:** 8 passed, 0 failed, 58 deprecation warnings (SQLAlchemy `utcnow()` and Pydantic v2 config syntax — no functional impact).

---

## Limitations

- **Simulation-only by default**: `RazorpayProvider` is implemented but requires valid Razorpay Test Mode credentials. Without them, all payment operations go through `SimulationProvider`.
- **Notification delivery is simulated**: The system logs notification events to the audit trail, but does not integrate with a real SMS, email, or WhatsApp gateway.
- **Recurring charge is a stub**: `RazorpayProvider.charge_saved_card` raises `NotImplementedError` — a real tokenised-payment flow requires a mandate agreement token that is outside the scope of this project.
- **Single-node scheduler**: `InMemoryScheduler` uses a Python daemon thread. This is suitable for demo purposes; a production deployment would replace it with a task queue (Celery, Temporal, etc.).
- **Benchmark is synthetic**: The 50-case evaluation dataset is hand-crafted. Recovery-rate figures should not be projected onto production traffic.
- **100% accuracy is deterministic**: In offline mode, the fallback maps failure codes deterministically to the same ground-truth labels used to score accuracy. This is a measure of the correctness of the rule engine, not generalisation from a live LLM.
- **SQLite only**: The default storage is SQLite. A production deployment would use PostgreSQL.

---

## Future Improvements

- Replace `InMemoryScheduler` with a durable task queue (Celery + Redis)
- Implement real email / SMS delivery via SendGrid / Twilio
- Add real recurring-mandate tokenised charging via Razorpay e-NACH
- Migrate to PostgreSQL with Alembic migrations
- Add a live LLM evaluation that measures accuracy on out-of-distribution failure codes not present in the training dataset
- Add multi-merchant isolation and merchant-specific policy configuration
- Add webhook retry handling for transient delivery failures

---

## Razorpay Buildathon 2026 — Track 03

This project was built for **Track 03: AI-Powered Business Automation** of the Razorpay Buildathon 2026.

**Core Razorpay concepts demonstrated:**
- Webhook ingestion and HMAC signature verification (`RAZORPAY_WEBHOOK_SECRET`)
- Payment link creation via Razorpay Payment Links API (`/v1/payment_links`)
- Live Razorpay provider client with Basic Auth (`RazorpayProvider`)
- Idempotency using Razorpay event IDs to deduplicate webhook deliveries
- Razorpay-format webhook payload parsing (both `payment.captured` and `payment.failed` events)

> All Razorpay API calls go through `SimulationProvider` by default. Configure `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` with Test Mode credentials to switch to live API calls.

---

## License

MIT
