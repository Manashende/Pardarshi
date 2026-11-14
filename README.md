# Pardarshi

**A multi-party threshold-cryptography system to prevent examination paper leaks in India.**

Pardarshi is designed so that no single person, location, or stage of the pipeline can ever access a complete, usable question paper before its authorised release time. Questions are encrypted at rest, assembled automatically without human review, and protected by a key that is split among independent custodians. The paper can be reconstructed only when a threshold of custodians submit their shares **and** an NTP-verified unlock time has been reached.

---

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [Roles](#roles)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Security design](#security-design)

---

## Overview

- **CBT is the primary mode.** There is no early release. The paper unlocks only at the exact exam start time, verified against multiple NTP sources, and is delivered directly to candidates with answer keys removed.
- **PRINT is the secondary mode** for regions that still need pen-and-paper exams. Reconstruction may begin a configurable number of hours before the exam, but only after a required number of distinct on-site officials confirm their physical presence.
- **Board-agnostic.** Subjects, question counts, centres and delivery mode are configured by administrators rather than hardcoded.
- **No grading.** Candidate submissions are stored and ledger-logged; grading is outside the scope of the system.

## Features

| Area | Description |
|---|---|
| **Threshold cryptography** | AES-256-GCM paper encryption with Shamir's Secret Sharing implemented from scratch over a 521-bit prime field. Every paper variant has its own independent key and split. |
| **Time verification** | Cross-checks two or more NTP servers and returns `CROSS_VERIFIED`, `SINGLE_SOURCE`, `UNVERIFIED_LOCAL` or `DISAGREEMENT_FLAGGED`. Only `CROSS_VERIFIED` is accepted for a standard unlock. |
| **Four-condition access gate** | Every sensitive action checks role, approved device, geofence (geodesic distance) and time window. Each attempt is recorded, whether allowed or denied. |
| **Item bank** | Questions are encrypted at rest and locked on submission. Selection and assembly run server-side, balanced by subject, difficulty and topic. No human views an assembled paper. |
| **Variant assignment** | HMAC-based, deterministic but unpredictable centre-to-variant mapping. Only the hash of the secret is stored. |
| **Dual-control compile** | One admin proposes and a different admin confirms. The live queue hides the proposer, while the ledger records both identities. |
| **Custodian unlock policy** | A standard threshold applies until a deadline, after which a higher override threshold applies. Submitted shares are verified against the server's record. |
| **Candidate allocation** | Three ranked centre preferences per student, processed in submission order, with a nearest-centre fallback when all preferences are full. |
| **Hash-chained ledger** | Append-only audit log with chain verification. Admins see a redacted view; auditors see full detail. |
| **Auditor governance** | Existing auditors vote (2-of-N) to activate new auditors. Admins cannot approve auditors, apart from a one-time bootstrap. |
| **Contributor identity reveal** | An admin requests a reveal, two distinct auditors approve, and only the requesting admin can view the identity. Every step is ledger-logged. |
| **Exam-taking interface** | Full-screen CBT view with countdown timer, auto-submit and submit-once enforcement. |
| **Print dispatch simulation** | Parallel dispatch across a centre's printers, calibrated to a CBSE-reported rate of 450 papers in 90 minutes on one printer. |

## Roles

| Role | Responsibilities |
|---|---|
| **Admin** | Registers centres, manages topics, creates, edits and cancels exam events, proposes and confirms compiles (never their own), runs candidate allocation, requests contributor reveals |
| **Auditor** | Read-only oversight, full ledger access, votes on new auditors and reveal requests |
| **Contributor** | Drafts questions locally and submits them once (locked) |
| **Custodian** | Registers a device and submits standard or override shares |
| **Centre Operator** | Confirms presence (PRINT) and requests unlock for the assigned centre |
| **Student** | Applies with three ranked centre preferences, takes the exam and submits once |

Separation-of-duties rules, such as no self-confirmation, no self-approval, and creators being unable to propose their own compile, are enforced server-side.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL |
| Cryptography | `cryptography` (AES-256-GCM), Shamir's Secret Sharing (custom implementation) |
| Authentication | JWT (`python-jose`), `bcrypt` |
| Time verification | `ntplib` |
| Geolocation | `geopy` |
| Frontend | React (JavaScript), Vite |
| UI components | MUI (`@mui/material`, `@mui/x-date-pickers`), `date-fns` |

## Getting started

### Prerequisites

- Python 3.13
- Node.js 18 or later and npm
- A PostgreSQL database

### 1. Clone the repository

```bash
git clone https://github.com/Manashende/Pardarshi.git
cd Pardarshi
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv

# Windows (PowerShell)
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in `backend/` (see [Configuration](#configuration)), then create the database schema:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Start the API server:

```bash
uvicorn app.main:app --reload
```

| Resource | URL |
|---|---|
| API base | `http://127.0.0.1:8000/api/v1` |
| Swagger UI | `http://127.0.0.1:8000/docs` |

### 3. Set up the frontend

```bash
cd frontend
npm install
```

Create a `.env` file in `frontend/` (see [Configuration](#configuration)), then start the development server:

```bash
npm run dev
```

The application is served at `http://localhost:5173`. The backend's CORS configuration allows `localhost:5173` and `127.0.0.1:5173`.

## Configuration

### Backend (`backend/.env`)

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME
JWT_SECRET=<long random string>
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
NTP_SERVERS=pool.ntp.org,time.google.com
ITEM_BANK_ENCRYPTION_KEY=<64 hex characters>
CUSTODIAN_SHARE_ENCRYPTION_KEY=<64 hex characters>
```

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | Secret used to sign JSON Web Tokens |
| `JWT_ALGORITHM` | Signing algorithm (`HS256`) |
| `JWT_EXPIRY_MINUTES` | Token lifetime in minutes |
| `NTP_SERVERS` | Comma-separated list of NTP hosts used for time verification |
| `ITEM_BANK_ENCRYPTION_KEY` | 64-character hex key that encrypts question content at rest |
| `CUSTODIAN_SHARE_ENCRYPTION_KEY` | 64-character hex key that encrypts custodian shares at rest. Must differ from the item bank key |

Generate each 64-character hex key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Frontend (`frontend/.env`)

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

## Security design

The threat model considers insiders who each hold part of the pipeline (administrators, custodians, centre operators and contributors), an outsider with database access, and a party tampering with the audit trail.

| Control | Protects against |
|---|---|
| Shamir threshold split with per-variant keys | Any single custodian or administrator reconstructing a paper; one variant's key exposing another |
| NTP cross-verified exact-time unlock | Early release through a single manipulated clock |
| Four-condition access gate | Unapproved devices, wrong locations, wrong roles and out-of-window actions, with every attempt recorded |
| Operator-to-centre assignment check | An operator unlocking a centre they are not assigned to |
| PRINT presence confirmations | Reconstruction before named on-site officials confirm presence |
| Item bank encryption and automated assembly | Any human reading an assembled paper; plaintext question content in storage |
| Share encryption at rest | Stolen database or backup |
| Dual-control compile with anonymous queue | One admin unilaterally selecting custodians; real-time collusion through the interface |
| Auditor self-governance | The audited party controlling who audits it |
| Two-auditor contributor reveal | Browsing contributor identities without independent approval |
| Admin ledger redaction | An admin learning which named custodians serve on an exam |
| Hash-chained ledger | Undetected edits to audit history |
| Answer-stripped CBT delivery | Answer keys reaching candidates |
| Submit-once locks | Edits or resubmission of questions, applications and exam attempts |