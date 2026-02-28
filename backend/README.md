# TalentOrbit — Backend API

**Django 6 + Django REST Framework**  
Production-quality Python backend serving the TalentOrbit platform.

---

## Stack
| Layer | Technology |
|---|---|
| Framework | Django 6 + DRF 3.16 |
| Auth | JWT via `djangorestframework-simplejwt` |
| CORS | `django-cors-headers` |
| Database (dev) | SQLite |
| Database (prod) | PostgreSQL |
| Static Files | WhiteNoise |
| Media Files | Pillow |

---

## Getting Started

```bash
# 1. Navigate to the backend folder
cd backend

# 2. Activate the virtualenv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. (Optional) Create a superuser for the /admin panel
python manage.py createsuperuser

# 6. Start the server (runs on port 8000)
python manage.py runserver
```

---

## API Reference — `v1`

### 🔑 Authentication  `POST /api/v1/auth/...`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/register/talent/` | Public | Register a new Talent account |
| `POST` | `/register/company/` | Public | Register a new Company account |
| `POST` | `/login/` | Public | Login — returns JWT access + refresh tokens |
| `POST` | `/refresh/` | Public | Refresh an access token |
| `POST` | `/logout/` | Public (body: refresh token) | Blacklist refresh token; no auth header required |
| `GET` | `/me/` | JWT | Get current user + profile |
| `PATCH` | `/profile/talent/` | JWT (Talent) | Update Talent profile |
| `PATCH` | `/profile/company/` | JWT (Company) | Update Company profile |
| `POST` | `/change-password/` | JWT | Change password |
| `POST` | `/password-reset/` | Public | Not implemented; returns 503. Use for “Forgot password?” until implemented. |
| `POST` | `/extract-resume/` | Public | Upload PDF/DOCX/TXT resume; returns extracted skills and bio (max 10 MB). |
| `GET` | `/2fa/setup/` | JWT | Get TOTP QR and secret for 2FA setup (use over HTTPS only). |
| `POST` | `/2fa/verify/` | JWT | Verify OTP and enable 2FA. |

---

### 💼 Jobs  `POST /api/v1/jobs/...`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/` | Public | List all open jobs (filter: `work_mode`, `job_type`, `skill`, search) |
| `GET` | `/<id>/` | Public | Retrieve a single job post |
| `POST` | `/<id>/apply/` | JWT (Talent) | Apply to a job |
| `GET` | `/saved/` | JWT (Talent) | View saved jobs |
| `POST` | `/saved/` | JWT (Talent) | Save a job |
| `DELETE` | `/saved/<id>/` | JWT (Talent) | Remove a saved job |
| `GET` | `/applications/` | JWT (Talent) | My applications |
| `DELETE` | `/applications/<id>/` | JWT (Talent) | Withdraw application |
| `GET` | `/mine/` | JWT (Company) | Company's own job posts |
| `POST` | `/mine/` | JWT (Company) | Create a job post |
| `PUT/PATCH` | `/mine/<id>/` | JWT (Company) | Update own job post |
| `DELETE` | `/mine/<id>/` | JWT (Company) | Delete own job post |
| `GET` | `/<id>/applications/` | JWT (Company) | See all applicants |
| `PATCH` | `/applications/<id>/status/` | JWT (Company) | Update applicant status |

---

### ✉️ Messaging  `/api/v1/messages/...`

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/` | JWT | List my threads |
| `POST` | `/thread/` | JWT | Start a new thread (dedup-safe) |
| `GET` | `/<thread_id>/messages/` | JWT | Fetch messages (marks read) |
| `POST` | `/send/` | JWT | Send a message |
| `GET` | `/unread/` | JWT | Total unread count |

---

## Authentication Flow (Frontend)

```js
// 1. Login
const { data } = await axios.post('/api/v1/auth/login/', { email, password });
localStorage.setItem('access', data.access);
localStorage.setItem('refresh', data.refresh);

// 2. Make authed requests
axios.defaults.headers['Authorization'] = `Bearer ${localStorage.getItem('access')}`;

// 3. Refresh silently when 401 received
```

---

## Data Models

```
User (email, full_name, role: TALENT|COMPANY|ADMIN)
  ├── TalentProfile (bio, skills[], resume, portfolio_url, subscription_tier)
  └── CompanyProfile (legal_name, industry, mission_statement, logo)

JobPost (company, title, job_type, work_mode, salary_range, skills_required, status)
  └── Application (applicant, job, cover_letter, status: 7-stage workflow)
  └── SavedJob (user, job)

Thread (participants: M2M, job?)
  └── Message (sender, body, attachment, read)
```

---

## Django Admin
Visit `http://localhost:8000/admin/` — manage all entities with a built-in CRUD interface.

---

## Production deployment

- **SECRET_KEY:** Must be set in the environment when `DEBUG=False`. Do not use the dev fallback in production.
- **CORS:** Set `CORS_ALLOWED_ORIGINS` to a comma-separated list of your frontend origins (e.g. `https://app.talentorbit.com`). Do not rely on the default `localhost` value.
- **ALLOWED_HOSTS:** Set to your production host(s), comma-separated.
- **FRONTEND_URL:** Set to the canonical frontend URL (used for Stripe redirects and links).
- **Stripe:** Set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`. In production, webhook signature verification is required; unset `STRIPE_WEBHOOK_SECRET` only in dev (`DEBUG=True`).
- **Database:** Use PostgreSQL in production; set `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` accordingly.
- **2FA:** The 2FA setup endpoint returns the TOTP secret in the response for manual entry. Use over **HTTPS only** in production; do not log the response.
- **Admin API:** Admin API requires `role == 'ADMIN'` and `is_staff`. Grant staff via Django admin or `createsuperuser`.
- **Courses:** `GET /api/v1/courses/` returns all courses for any authenticated user (global catalog). Filter by role or visibility in the app if needed.
