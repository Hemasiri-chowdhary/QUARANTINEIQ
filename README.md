# QuarantineIQ 

QuarantineIQ connects GitHub Actions evidence with persistent engineering memory from Hindsight. It investigates failing CI tests, surfaces relevant past experiences, challenges risky quarantines, records the human decision and outcome, and feeds confirmed lessons back into memory.

## Core workflow

GitHub Actions → ingestion → current failure/code context → Hindsight recall → attention score → recommendation → Decision Challenger → human decision → outcome → Hindsight learning → future investigation

## V3 capabilities

- GitHub repository and GitHub Actions workflow/run/job ingestion
- Failed-job log capture when available
- Commit and changed-file context
- `workflow_run` webhook ingestion with signature validation and idempotency
- Cross-test/service semantic Hindsight retrieval
- Evidence-backed root-cause signals
- Decision Challenger
- Recurring failure patterns / potential blind spots
- Activity and challenge history
- Live vs demo data separation
- Human decision + outcome learning loop
- Async-safe Hindsight integration for FastAPI

## Windows setup

### 1. Create/activate the Python environment

```powershell
cd C:\path\to\QUARANTINEIQ_V3
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Hindsight

Run Hindsight in a separate terminal:

```powershell
$env:HINDSIGHT_API_LLM_PROVIDER="groq"
$env:HINDSIGHT_API_LLM_API_KEY="YOUR_GROQ_API_KEY"
$env:HINDSIGHT_API_LLM_MODEL="openai/gpt-oss-20b"
$env:HINDSIGHT_API_LLM_GROQ_SERVICE_TIER="on_demand"
hindsight-api
```

Keep it running.

### 3. Configure `.env`

Copy `.env.example` to `.env` and set the GitHub values for live mode. Do not commit secrets.

```text
HINDSIGHT_URL=http://localhost:8888
HINDSIGHT_BANK_ID=quarantineiq-experiences
GITHUB_REPOSITORY=owner/repository
GITHUB_TOKEN=your_token
GITHUB_WEBHOOK_SECRET=your_secret
```

### 4. Seed the local demo data

```powershell
python scripts\seed_demo.py
```

This creates the V1/V2-compatible demo dataset and attempts to retain the stable demo experiences in Hindsight when Hindsight is available.

### 5. Start the backend

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

### 6. Start the frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Live GitHub mode

The backend reads the configured repository and token server-side. The GitHub page supports repository verification and manual sync.

For near-real-time updates, configure a repository webhook:

- Event: `workflow_run`
- Payload URL: `https://YOUR_PUBLIC_HOST/api/github/webhook`
- Content type: `application/json`
- Secret: the same value as `GITHUB_WEBHOOK_SECRET`

The included workflow:

`.github/workflows/quarantineiq-v3-ci.yml`

prints a recognizable test failure and supports a manual `simulate_failure=true` run after the workflow is pushed to GitHub.

## Verification

With Hindsight and the backend running:

```powershell
python backend\test_hindsight.py
python scripts\verify_v3.py
```

Then:

```powershell
cd frontend
npm run build
```

## Security

Keep GitHub tokens, Groq keys, Hindsight keys, and webhook secrets only in environment variables. Never commit them.
