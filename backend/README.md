# Welcome to TalentOrbit Backend

Hey there! 👋

This is the backend API powering TalentOrbit—a modern platform for talent management, recruitment, and company growth. Built with Django 6 and Django REST Framework, it’s designed for reliability, security, and developer happiness.

---

## What is TalentOrbit?
TalentOrbit connects job seekers and companies, making hiring and career growth easier, smarter, and more transparent. Whether you’re a developer, recruiter, or founder, this backend is the engine behind:
- Job posting and applications
- Secure authentication (JWT, 2FA)
- Messaging between users
- Company and talent profiles
- Subscription management
- Admin controls
- And much more

---

## Tech Stack
- **Framework:** Django 6, Django REST Framework
- **Auth:** JWT (via SimpleJWT), optional 2FA
- **Database:** SQLite (dev), PostgreSQL (production)
- **Static/Media:** WhiteNoise, Pillow
- **CORS:** django-cors-headers

---

## Getting Started (Local Development)
1. **Clone the repo & enter the backend folder:**
   ```bash
   cd backend
   ```
2. **Activate your Python virtual environment:**
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Apply migrations:**
   ```bash
   python manage.py migrate
   ```
5. **Create a superuser (optional, for admin panel):**
   ```bash
   python manage.py createsuperuser
   ```
6. **Run the server:**
   ```bash
   python manage.py runserver
   ```
   The API will be live at [http://localhost:8000](http://localhost:8000)

---

## API Overview

### Authentication
- Register as Talent or Company
- Login (JWT access/refresh)
- Profile management
- Password change/reset
- 2FA setup & verification

### Jobs
- List, view, create, update, delete jobs
- Apply to jobs
- Save jobs, withdraw applications
- Company job management

### Messaging
- Threaded conversations
- Send/receive messages
- Unread count

### Example: Login Flow
```js
// Login
const { data } = await axios.post('/api/v1/auth/login/', { email, password });
localStorage.setItem('access', data.access);
localStorage.setItem('refresh', data.refresh);
// Authenticated requests
axios.defaults.headers['Authorization'] = `Bearer ${localStorage.getItem('access')}`;
```

---

## Data Models (Simplified)
```
User (email, full_name, role: TALENT|COMPANY|ADMIN)
  ├── TalentProfile (bio, skills[], resume, portfolio_url, subscription_tier)
  └── CompanyProfile (legal_name, industry, mission_statement, logo)
JobPost (company, title, job_type, work_mode, salary_range, skills_required, status)
  └── Application (applicant, job, cover_letter, status)
# Backend README (Consolidated)

This repository's Backend documentation has been consolidated into the project's root `README.md` to provide a single, canonical source of truth.

Please see the top-level `README.md` for full Frontend, Backend, and Infrastructure guides:

- [README.md](../README.md)

If you need a focused backend-only doc kept in this file, tell me and I will extract the backend sections back into `backend/README.md`.

