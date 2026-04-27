# Playto KYC Pipeline

KYC onboarding service for Playto Pay. Merchants submit identity and business documents; reviewers approve or reject submissions through a clean state machine.

**Stack:** Django + DRF · React + Tailwind · SQLite (dev) / PostgreSQL (prod) · Supabase Storage (files)

---

## Quick Start (Local)

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env           # edit values as needed
python manage.py migrate
python seed.py                    # creates test users
python manage.py runserver
```

Backend runs at `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Frontend runs at `http://localhost:5173`

---

## Demo Credentials

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Reviewer | `reviewer1` | `Reviewer@123` | Can see all submissions |
| Merchant | `merchant1` | `Merchant@123` | Submission in **draft** |
| Merchant | `merchant2` | `Merchant@123` | Submission **under review** (AT RISK — >24h) |

---

## API Reference

All endpoints under `/api/v1/`. Token auth: `Authorization: Token <token>`

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register/` | Create account |
| POST | `/auth/login/` | Get token |
| GET | `/auth/me/` | Current user |

### Merchant
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/kyc/my-submission/` | Get own submission |
| POST | `/kyc/my-submission/` | Create draft |
| PUT | `/kyc/my-submission/` | Update draft (multipart) |
| POST | `/kyc/my-submission/submit/` | Submit for review |

### Reviewer
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/kyc/queue/` | Active queue, oldest first |
| GET | `/kyc/submissions/` | All submissions (filter: `?status=approved`) |
| GET | `/kyc/submissions/<id>/` | Submission detail |
| POST | `/kyc/submissions/<id>/transition/` | Change state |
| GET | `/kyc/metrics/` | Dashboard metrics |
| GET | `/kyc/notifications/` | Notification event log |

### Transition payload
```json
{ "new_state": "approved", "note": "All documents verified." }
```

### Error shape (all errors)
```json
{ "error": "Cannot move from 'approved' to 'draft'. ...", "code": "invalid_transition" }
```

---

## State Machine

```
draft → submitted → under_review → approved (terminal)
                                 → rejected (terminal)
                                 → more_info_requested → submitted
```

---

## Running Tests

```bash
cd backend
source venv/bin/activate
python manage.py test kyc --verbosity=2
```

18 tests covering: state machine (legal + illegal transitions), file validation (size + magic bytes), auth isolation, SLA tracking.

---

## Supabase Setup (optional)

1. Create a Supabase project
2. Go to Storage → create bucket `kyc-documents` (public)
3. Copy URL and service role key to `.env`

Without Supabase configured, files are saved to `backend/media/` locally.

---

## Deployment (Render)

### Backend (Web Service)
- **Build:** `pip install -r requirements.txt && python manage.py migrate && python seed.py`
- **Start:** `gunicorn config.wsgi`
- **Env vars:** `SECRET_KEY`, `DEBUG=False`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `CORS_ALLOWED_ORIGINS`

### Frontend (Static Site)
- **Build:** `npm install && npm run build`
- **Publish dir:** `dist`
- **Env var:** `VITE_API_URL=https://your-backend.onrender.com`
