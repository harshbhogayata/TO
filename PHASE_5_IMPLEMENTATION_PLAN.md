# 🧠 TalentOrbit — Phase 5: Data & Intelligence
## Enterprise-Grade Implementation Plan (No Compromise)

**Date:** March 2, 2026  
**Quality Bar:** Trillion-dollar company standard. No MVPs, no shortcuts, no simplifications.  
**Constraint:** All third-party services must be free tier.

---

## 📋 TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [New Django App: `intelligence`](#2-new-django-app-intelligence)
3. [Component 1: Recommendation Engine (Real-Time ML Inference)](#3-component-1-recommendation-engine)
4. [Component 2: Resume Parsing with NLP (spaCy)](#4-component-2-resume-parsing-with-nlp)
5. [Component 3: Company Dashboard Analytics](#5-component-3-company-dashboard-analytics)
6. [Component 4: A/B Testing Framework (PostHog Feature Flags)](#6-component-4-ab-testing-framework)
7. [Component 5: Data Warehouse + ETL Pipeline](#7-component-5-data-warehouse--etl-pipeline)
8. [File Manifest (Every File That Will Be Created/Modified)](#8-file-manifest)
9. [Database Models (Complete Schema)](#9-database-models)
10. [API Endpoints (Complete Specification)](#10-api-endpoints)
11. [Celery Tasks (Complete Specification)](#11-celery-tasks)
12. [Frontend Design Requirements](#12-frontend-design-requirements)
13. [Dependencies](#13-dependencies)
14. [Migration & Deployment](#14-migration--deployment)

---

## 1. ARCHITECTURE OVERVIEW

### What Exists Today (Codebase Snapshot)

```
accounts/models.py:
  - User (email, role: TALENT|COMPANY|ADMIN, avatar, 2FA, etc.)
  - TalentProfile (bio, location, resume, skills: JSONField, is_open_to_work, search_vector, subscription_tier)
  - CompanyProfile (legal_name, industry, mission_statement, logo, headquarters, search_vector, subscription_tier)

jobs/models.py:
  - JobPost (company FK, title, description, requirements, responsibilities, job_type, work_mode, status, experience_level, location, salary_min/max, skills_required: JSONField, search_vector, views_count)
  - Application (applicant FK, job FK, cover_letter, status: pending→reviewing→shortlisted→interviewing→offered→rejected→withdrawn, notes)
  - SavedJob (user FK, job FK)

search/models.py:
  - SearchAnalytics (query, normalized_query, entity_type, user FK, results_count, clicked_result_id, clicked_position, filters_applied, response_time_ms)

messaging/models.py:
  - Thread (participants M2M, job FK optional)
  - Message (thread FK, sender FK, body, attachment, read, read_at)

notifications/models.py:
  - Notification (user FK, category, title, description, is_read)

courses/models.py:
  - Course (category, module_name, title, duration, img_url, url, is_coming_soon)
```

### Current match_score (TO BE REPLACED)

In `jobs/serializers.py` → `JobPostSerializer.get_match_score()`:
- Simple set intersection: `len(talent_skills ∩ job_skills) / len(job_skills) * 100`
- Computed per-request, no ML, no collaborative signals, no normalization
- Same basic logic duplicated in `search/serializers.py` → `JobSearchResultSerializer.get_match_score()`

### Phase 5 Architecture (What We're Building)

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE LAYER                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Recommender   │  │ Resume       │  │ Analytics Engine      │ │
│  │ Engine        │  │ Parser (NLP) │  │ (ETL + Warehouse)     │ │
│  │               │  │              │  │                       │ │
│  │ • TF-IDF      │  │ • spaCy NER  │  │ • Materialized Views  │ │
│  │   Vectorizer  │  │ • Custom     │  │ • Aggregation Tables  │ │
│  │ • Cosine Sim  │  │   Pipeline   │  │ • Periodic ETL Tasks  │ │
│  │ • Collab.     │  │ • Skill      │  │ • Hiring Funnels      │ │
│  │   Filtering   │  │   Taxonomy   │  │ • Time-to-Hire        │ │
│  │ • Hybrid      │  │ • Experience │  │ • Source Analytics     │ │
│  │   Scorer      │  │   Extraction │  │ • Cohort Analysis     │ │
│  │ • Real-Time   │  │ • Education  │  │ • Benchmark Metrics   │ │
│  │   Inference   │  │   Parsing    │  │                       │ │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘ │
│         │                 │                       │             │
│  ┌──────┴─────────────────┴───────────────────────┴───────────┐ │
│  │              A/B Testing Framework                          │ │
│  │  • PostHog Feature Flags (Server + Client)                  │ │
│  │  • Experiment Tracking + Conversion Events                  │ │
│  │  • Django Middleware + React Hook                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
         │                 │                       │
    ┌────┴────┐      ┌────┴────┐            ┌────┴────┐
    │ Redis   │      │ Celery  │            │ Neon PG │
    │ Cache   │      │ Workers │            │ Database│
    └─────────┘      └─────────┘            └─────────┘
```

---

## 2. NEW DJANGO APP: `intelligence`

A single new app that owns all Phase 5 logic. Clean separation from existing apps.

```
backend/intelligence/
├── __init__.py
├── apps.py
├── admin.py
├── models.py                    # All Phase 5 data models
├── serializers.py               # All Phase 5 serializers
├── views.py                     # All Phase 5 API views
├── urls.py                      # URL routing
├── signals.py                   # Post-save hooks for re-computation
├── tasks.py                     # Celery async tasks (ETL, model training, parsing)
├── permissions.py               # Custom permissions for analytics endpoints
├── constants.py                 # Skill taxonomy, weight configs, thresholds
├── migrations/
│   └── __init__.py
│
├── engine/                      # Recommendation engine internals
│   ├── __init__.py
│   ├── vectorizer.py            # TF-IDF skill vectorization + cosine similarity
│   ├── collaborative.py         # Collaborative filtering (user-job interaction matrix)
│   ├── content_based.py         # Content-based scoring (skills, experience, location)
│   ├── hybrid.py                # Hybrid combiner (weighted ensemble)
│   ├── features.py              # Feature extraction from User/Job/Application data
│   └── cache.py                 # Recommendation cache layer (Redis)
│
├── nlp/                         # NLP pipeline for resume parsing
│   ├── __init__.py
│   ├── parser.py                # Main resume parsing orchestrator
│   ├── extractors.py            # Skill, education, experience extractors
│   ├── taxonomy.py              # Canonical skill taxonomy + synonym mapping
│   ├── patterns.py              # Regex + spaCy patterns for entity extraction
│   └── normalizer.py            # Text cleaning, section detection
│
├── analytics/                   # Data warehouse + ETL
│   ├── __init__.py
│   ├── warehouse.py             # ETL pipeline orchestrator
│   ├── aggregators.py           # Metric computation (funnel, time-to-hire, etc.)
│   ├── materialized.py          # Materialized view management
│   └── benchmarks.py            # Platform-wide benchmark computations
│
└── experiments/                 # A/B testing framework
    ├── __init__.py
    ├── client.py                # PostHog server-side client wrapper
    ├── middleware.py             # Django middleware for experiment assignment
    ├── decorators.py            # View decorators for experiment gating
    └── tracking.py              # Event tracking helpers
```

---

## 3. COMPONENT 1: RECOMMENDATION ENGINE

### 3.1 Architecture: Real-Time Hybrid ML Inference

This is NOT a simple pre-computed table. This is a **real-time inference pipeline** that computes recommendations on-the-fly with sub-100ms latency via aggressive caching and efficient vectorization.

```
Request Flow:
  GET /api/v1/intelligence/recommendations/jobs/
    │
    ├─ [1] Check Redis cache → HIT? Return instantly (<5ms)
    │
    ├─ [2] MISS: Load user feature vector (skills TF-IDF + behavior signals)
    │        │
    │        ├─ Skills vector: TF-IDF over canonical skill taxonomy
    │        ├─ Behavior vector: application history, saved jobs, search clicks
    │        └─ Profile vector: experience_level, location, salary preferences
    │
    ├─ [3] Content-Based Score (per candidate job):
    │        │
    │        ├─ Skill cosine similarity (TF-IDF vectors)
    │        ├─ Experience level match (ordinal distance)
    │        ├─ Location match (exact/region/remote boost)
    │        ├─ Salary range overlap score
    │        └─ Work mode preference match
    │
    ├─ [4] Collaborative Filtering Score:
    │        │
    │        ├─ User-Job interaction matrix (applications, saves, views, clicks)
    │        ├─ Find K nearest neighbor users (cosine sim on interaction vectors)
    │        ├─ Aggregate neighbor preferences → score unseen jobs
    │        └─ Implicit feedback signals (time-on-page from SearchAnalytics)
    │
    ├─ [5] Popularity Signal:
    │        │
    │        ├─ views_count (decayed by age)
    │        ├─ application_count (strong positive signal)
    │        └─ save_count (medium positive signal)
    │
    ├─ [6] Freshness Boost:
    │        │
    │        └─ Exponential decay: score *= e^(-λ * days_since_posted)
    │
    ├─ [7] Hybrid Combiner (Weighted Ensemble):
    │        │
    │        ├─ final = w_content * content_score
    │        │        + w_collab * collab_score
    │        │        + w_popularity * popularity_score
    │        │        + w_freshness * freshness_boost
    │        │
    │        ├─ Weights are A/B testable via feature flags
    │        └─ Default: content=0.45, collab=0.30, popularity=0.15, freshness=0.10
    │
    ├─ [8] Post-processing:
    │        │
    │        ├─ Filter out already-applied jobs
    │        ├─ Filter out expired jobs
    │        ├─ Diversity injection (no more than 3 jobs from same company)
    │        └─ Explain: return breakdown of why each job was recommended
    │
    └─ [9] Cache result in Redis (TTL: 15 min per user, busted on new application/save)
```

### 3.2 TF-IDF Vectorizer (intelligence/engine/vectorizer.py)

- Uses `scikit-learn`'s `TfidfVectorizer` trained on the **full skill corpus** from all JobPosts + TalentProfiles
- The vectorizer model is trained periodically via Celery task (daily) and cached in Redis as pickled bytes
- At inference time, transforms user skills and job skills into TF-IDF vectors
- Cosine similarity computed via `sklearn.metrics.pairwise.cosine_similarity`
- **Canonical skill taxonomy** normalizes "React.js" → "react", "ReactJS" → "react", "React" → "react"
- Handles multi-word skills: "Machine Learning", "Natural Language Processing"

### 3.3 Collaborative Filtering (intelligence/engine/collaborative.py)

- Builds a **sparse user-item interaction matrix** from:
  - Applications (weight: 5.0 — strongest signal)
  - Saved jobs (weight: 3.0)
  - Search result clicks (weight: 2.0 — from SearchAnalytics.clicked_result_id)
  - Job views (weight: 1.0 — implicit, from views_count attribution)
- Uses **implicit ALS (Alternating Least Squares)** via the `implicit` library (free, open-source)
  - Alternatively, a simpler KNN approach with cosine similarity on the interaction matrix if `implicit` is too heavy
- Cold-start handling: for users with <3 interactions, fall back to pure content-based
- For new jobs with 0 interactions, use content similarity to existing popular jobs

### 3.4 Hybrid Scorer (intelligence/engine/hybrid.py)

- Combines all signals with configurable weights
- Weights are pulled from PostHog feature flags for A/B testing
- Returns a `RecommendationResult` dataclass with:
  - `job_id`, `final_score`, `content_score`, `collab_score`, `popularity_score`, `freshness_score`
  - `explanation`: human-readable string ("Strong skill match (React, Python) + similar users applied")
  - `match_breakdown`: dict with per-factor scores

### 3.5 Replacing the Current match_score

The current `JobPostSerializer.get_match_score()` and `JobSearchResultSerializer.get_match_score()` will be **replaced** to call the recommendation engine's content-based scorer in real-time. The old simple intersection logic is deleted entirely.

### 3.6 Models

```python
class SkillTaxonomy(models.Model):
    """Canonical skill names with aliases/synonyms for normalization."""
    canonical_name = models.CharField(max_length=100, unique=True, db_index=True)
    category = models.CharField(max_length=100, blank=True)  # e.g., "Programming", "Design", "Management"
    aliases = models.JSONField(default=list)  # ["React.js", "ReactJS", "React"]
    embedding_vector = models.BinaryField(null=True, blank=True)  # Serialized numpy array
    is_verified = models.BooleanField(default=True)  # Admin-verified vs auto-detected
    usage_count = models.PositiveIntegerField(default=0)  # How many profiles/jobs use this skill
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class UserInteraction(models.Model):
    """Tracks all user-job interactions for collaborative filtering."""
    class InteractionType(models.TextChoices):
        VIEW = 'view', 'Viewed'
        CLICK = 'click', 'Search Click'
        SAVE = 'save', 'Saved'
        APPLY = 'apply', 'Applied'
        UNSAVE = 'unsave', 'Unsaved'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interactions')
    job = models.ForeignKey('jobs.JobPost', on_delete=models.CASCADE, related_name='interactions')
    interaction_type = models.CharField(max_length=20, choices=InteractionType.choices, db_index=True)
    weight = models.FloatField(default=1.0)  # Pre-computed weight for the interaction type
    metadata = models.JSONField(default=dict, blank=True)  # Extra context (search query, position, etc.)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'job', 'interaction_type'], name='idx_interaction_user_job_type'),
            models.Index(fields=['user', '-created_at'], name='idx_interaction_user_date'),
            models.Index(fields=['job', 'interaction_type'], name='idx_interaction_job_type'),
        ]

class RecommendationLog(models.Model):
    """Audit log for recommendation requests — enables offline evaluation."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recommendation_logs')
    recommended_jobs = models.JSONField(default=list)  # [{job_id, score, explanation}, ...]
    algorithm_version = models.CharField(max_length=50)  # "hybrid_v1", "hybrid_v2" etc.
    weights_used = models.JSONField(default=dict)  # {content: 0.45, collab: 0.30, ...}
    latency_ms = models.PositiveIntegerField()
    cache_hit = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

class ModelArtifact(models.Model):
    """Stores trained ML model artifacts (TF-IDF vectorizer, interaction matrix, etc.)"""
    name = models.CharField(max_length=100, unique=True)  # "tfidf_vectorizer", "interaction_matrix"
    version = models.PositiveIntegerField(default=1)
    artifact_data = models.BinaryField()  # Pickled model bytes
    metadata = models.JSONField(default=dict)  # {num_features, training_size, accuracy, etc.}
    trained_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('name', 'version')
```

### 3.7 API Endpoints

```
GET  /api/v1/intelligence/recommendations/jobs/
     → Returns top 20 recommended jobs for the authenticated talent user
     → Params: ?limit=20&exclude_applied=true&diversity=true
     → Response includes match_score, explanation, breakdown per job

GET  /api/v1/intelligence/recommendations/talent/?job_id=123
     → Returns top 20 recommended talent profiles for a job (company/admin only)
     → Params: ?job_id=123&limit=20
     → Response includes match_score, explanation per talent

GET  /api/v1/intelligence/match-score/?job_id=123
     → Returns detailed match breakdown for authenticated user vs. a specific job
     → Response: {score, breakdown: {skills: 0.8, experience: 0.6, location: 0.9, ...}, explanation}

POST /api/v1/intelligence/interactions/
     → Record a user interaction (view, click, save tracked automatically)
     → Body: {job_id, interaction_type, metadata}
```

### 3.8 Celery Tasks

```python
# Periodic: retrain TF-IDF vectorizer daily at 02:00 UTC
'intelligence.tasks.retrain_tfidf_vectorizer'  → queue='default', schedule=crontab(hour=2, minute=0)

# Periodic: rebuild interaction matrix daily at 02:30 UTC
'intelligence.tasks.rebuild_interaction_matrix' → queue='default', schedule=crontab(hour=2, minute=30)

# Periodic: update skill taxonomy usage counts daily at 03:30 UTC
'intelligence.tasks.update_skill_taxonomy'      → queue='default', schedule=crontab(hour=3, minute=30)

# Periodic: warm recommendation cache for active users at 04:00 UTC
'intelligence.tasks.warm_recommendation_cache'  → queue='default', schedule=crontab(hour=4, minute=0)
```

---

## 4. COMPONENT 2: RESUME PARSING WITH NLP

### 4.1 Architecture: spaCy-Powered Enterprise Resume Parser

This **replaces** the current naive regex-based `ExtractResumeView` in `accounts/views.py` (lines ~400-470) which uses a hardcoded `SKILLS_DB` list of 33 skills and simple `str.lower() in text` matching.

The new parser uses:
- **spaCy** with `en_core_web_sm` model for NER (Named Entity Recognition)
- **Custom EntityRuler** trained on the SkillTaxonomy table
- **Section detection** (Education, Experience, Skills, Projects) via heading pattern recognition
- **Date extraction** for work experience duration calculation
- **Education parsing** (degree, institution, graduation year)
- **Skill extraction** from both explicit skill sections AND contextual mentions

```
Resume Parsing Pipeline:
  Upload (PDF/DOCX/TXT)
    │
    ├─ [1] Text Extraction (PyPDF2 / python-docx — already in codebase)
    │
    ├─ [2] Text Normalization
    │        ├─ Unicode cleanup (remove ligatures, normalize whitespace)
    │        ├─ Section boundary detection (regex patterns for headings)
    │        └─ Bullet point normalization
    │
    ├─ [3] spaCy NLP Pipeline
    │        ├─ Tokenization
    │        ├─ POS tagging
    │        ├─ Named Entity Recognition (PERSON, ORG, DATE, GPE)
    │        ├─ Custom EntityRuler (SKILL entities from SkillTaxonomy)
    │        └─ Dependency parsing (for context understanding)
    │
    ├─ [4] Skill Extraction
    │        ├─ From explicit "Skills" section (highest confidence)
    │        ├─ From experience descriptions (contextual extraction)
    │        ├─ Normalize via SkillTaxonomy → canonical names
    │        ├─ Confidence scoring per skill (section weight + frequency)
    │        └─ Deduplication
    │
    ├─ [5] Experience Extraction
    │        ├─ Job title detection (custom patterns)
    │        ├─ Company name detection (ORG entities)
    │        ├─ Date range extraction (DATE entities + custom patterns)
    │        ├─ Duration calculation (years, months)
    │        └─ Total years of experience aggregation
    │
    ├─ [6] Education Extraction
    │        ├─ Degree detection ("Bachelor", "Master", "PhD", "B.S.", "M.S.", etc.)
    │        ├─ Institution detection (ORG entities near degree mentions)
    │        ├─ Field of study extraction
    │        └─ Graduation year detection
    │
    ├─ [7] Bio Generation
    │        ├─ Extract first person summary/objective section
    │        ├─ OR generate from extracted data: "{years} years experience in {top_skills}"
    │        └─ Truncate to 500 chars, ensure grammatical completeness
    │
    └─ [8] Return Structured Result
             {
               skills: [{name, canonical_name, confidence, source_section}],
               experience: [{title, company, start_date, end_date, duration_months, description}],
               education: [{degree, institution, field, graduation_year}],
               total_experience_years: float,
               bio: string,
               contact: {email, phone, linkedin, portfolio},  // bonus extraction
               raw_text: string  // for debugging
             }
```

### 4.2 Models

```python
class ParsedResume(models.Model):
    """Stores the result of NLP-based resume parsing. One per talent profile, updated on re-upload."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parsed_resume')
    raw_text = models.TextField(blank=True)  # Full extracted text
    parsed_skills = models.JSONField(default=list)  # [{name, canonical_name, confidence, source}]
    parsed_experience = models.JSONField(default=list)  # [{title, company, start, end, months, desc}]
    parsed_education = models.JSONField(default=list)  # [{degree, institution, field, year}]
    total_experience_years = models.FloatField(null=True, blank=True)
    generated_bio = models.TextField(blank=True, max_length=500)
    contact_info = models.JSONField(default=dict, blank=True)  # {email, phone, linkedin, portfolio}
    parser_version = models.CharField(max_length=50, default='spacy_v1')
    confidence_score = models.FloatField(default=0.0)  # Overall parsing confidence (0-1)
    parsed_at = models.DateTimeField(auto_now=True)
    source_file_hash = models.CharField(max_length=64, blank=True)  # SHA-256 of source file (skip re-parse if same)

    class Meta:
        verbose_name = 'Parsed Resume'
```

### 4.3 API Endpoints

```
POST /api/v1/intelligence/parse-resume/
     → Upload + parse resume. Returns structured extraction.
     → Replaces: POST /api/v1/auth/extract-resume/
     → Accepts: multipart/form-data with `resume` file
     → Response: Full parsed result (skills, experience, education, bio, etc.)
     → Side effect: Updates ParsedResume record + optionally updates TalentProfile.skills

POST /api/v1/intelligence/parse-resume/apply/
     → Apply parsed resume data to the user's TalentProfile
     → Body: {apply_skills: true, apply_bio: true, apply_experience: true}
     → Updates TalentProfile.skills, bio, etc.

GET  /api/v1/intelligence/parse-resume/
     → Returns the latest parsed resume data for the authenticated user

GET  /api/v1/intelligence/skills/taxonomy/
     → Returns the full skill taxonomy (for autocomplete, search, etc.)
     → Params: ?category=Programming&q=react&limit=50
```

### 4.4 Celery Tasks

```python
# On-demand: parse resume async (for large files)
'intelligence.tasks.parse_resume_async'  → queue='default'

# Periodic: rebuild spaCy EntityRuler from SkillTaxonomy (daily at 03:00 UTC)
'intelligence.tasks.rebuild_skill_entity_ruler'  → queue='default', schedule=crontab(hour=3, minute=0)

# Periodic: auto-detect new skills from job postings (weekly, Sunday 04:00 UTC)
'intelligence.tasks.discover_new_skills'  → queue='default', schedule=crontab(hour=4, minute=0, day_of_week=0)
```

### 4.5 Changes to Existing Code

1. **DELETE** the `ExtractResumeView` class and `SKILLS_DB` constant from `accounts/views.py`
2. **DELETE** the `extract-resume/` URL from `accounts/urls.py`
3. **UPDATE** the frontend to call `/api/v1/intelligence/parse-resume/` instead
4. **UPDATE** `TalentProfile` serializer to include `parsed_resume` data (nested, read-only)

---

## 5. COMPONENT 3: COMPANY DASHBOARD ANALYTICS

### 5.1 Architecture: Full Hiring Funnel Analytics

Real-time + pre-aggregated analytics for company dashboards. Companies see their hiring performance at a glance.

```
Analytics Dashboard Sections:

┌─────────────────────────────────────────────────────────────────┐
│ [1] HIRING FUNNEL                                               │
│                                                                 │
│   Views(1,247) → Apps(89) → Shortlisted(34) → Interview(12)    │
│     → Offered(5) → Hired(3)                                    │
│                                                                 │
│   Conversion rates between each stage                           │
│   Per-job breakdown + aggregate for all jobs                    │
│   Time period selector (7d, 30d, 90d, all-time)                │
├─────────────────────────────────────────────────────────────────┤
│ [2] TIME-TO-HIRE METRICS                                        │
│                                                                 │
│   Average days from posting → first application                 │
│   Average days from application → shortlist                     │
│   Average days from shortlist → offer                           │
│   Average total days from posting → hire                        │
│   Per-job breakdown with sparkline trend                        │
├─────────────────────────────────────────────────────────────────┤
│ [3] SOURCE ANALYTICS                                            │
│                                                                 │
│   Where do applicants find your jobs?                           │
│   • Direct (job board page views)                               │
│   • Search (which search queries led to views/applications)     │
│   • Recommendations (how many came from the recommendation      │
│     engine)                                                     │
│   Top search queries that led to applications for your jobs     │
├─────────────────────────────────────────────────────────────────┤
│ [4] TALENT POOL ANALYTICS                                       │
│                                                                 │
│   Skills distribution of applicants (bar chart)                 │
│   Experience level distribution (pie chart)                     │
│   Location heatmap of applicants                                │
│   Open-to-work vs. passive candidates                           │
├─────────────────────────────────────────────────────────────────┤
│ [5] PLATFORM BENCHMARKS                                         │
│                                                                 │
│   Your avg. time-to-hire vs. platform average                   │
│   Your application rate vs. platform average                    │
│   Your offer acceptance rate vs. platform average               │
│   Industry-specific benchmarks                                  │
├─────────────────────────────────────────────────────────────────┤
│ [6] JOB PERFORMANCE TABLE                                       │
│                                                                 │
│   Each active job with:                                         │
│   • Views, Applications, Shortlisted, Interviews, Offers       │
│   • Match quality score (avg. recommendation score of apps)     │
│   • Days active                                                 │
│   • Status indicator (healthy / underperforming / closing soon) │
│   Sortable, filterable, exportable                              │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Models (Analytics/Warehouse Tables)

```python
class HiringFunnelSnapshot(models.Model):
    """
    Pre-aggregated daily snapshot of hiring funnel metrics per company.
    Computed by ETL task. Enables fast O(1) dashboard queries.
    """
    company = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='funnel_snapshots')
    job = models.ForeignKey('jobs.JobPost', on_delete=models.CASCADE, null=True, blank=True, related_name='funnel_snapshots')  # null = aggregate for all jobs
    date = models.DateField(db_index=True)
    period = models.CharField(max_length=10, choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], default='daily')

    views = models.PositiveIntegerField(default=0)
    applications = models.PositiveIntegerField(default=0)
    reviewing = models.PositiveIntegerField(default=0)
    shortlisted = models.PositiveIntegerField(default=0)
    interviewing = models.PositiveIntegerField(default=0)
    offered = models.PositiveIntegerField(default=0)
    rejected = models.PositiveIntegerField(default=0)
    withdrawn = models.PositiveIntegerField(default=0)

    avg_time_to_review_hours = models.FloatField(null=True, blank=True)
    avg_time_to_shortlist_hours = models.FloatField(null=True, blank=True)
    avg_time_to_offer_hours = models.FloatField(null=True, blank=True)
    avg_time_to_hire_hours = models.FloatField(null=True, blank=True)

    avg_match_score = models.FloatField(null=True, blank=True)  # Avg recommendation score of applicants

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'job', 'date', 'period')
        indexes = [
            models.Index(fields=['company', '-date', 'period'], name='idx_funnel_company_date'),
            models.Index(fields=['job', '-date'], name='idx_funnel_job_date'),
        ]


class SourceAttribution(models.Model):
    """
    Tracks how users discovered a job post (search, direct, recommendation, etc.).
    One record per job-view or job-application with source attribution.
    """
    class Source(models.TextChoices):
        DIRECT = 'direct', 'Direct (Job Board)'
        SEARCH = 'search', 'Search'
        RECOMMENDATION = 'recommendation', 'Recommendation Engine'
        EXTERNAL = 'external', 'External Referral'
        NOTIFICATION = 'notification', 'Notification'

    job = models.ForeignKey('jobs.JobPost', on_delete=models.CASCADE, related_name='source_attributions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, db_index=True)
    search_query = models.CharField(max_length=500, blank=True)  # If source=search
    converted_to_application = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['job', 'source', '-created_at'], name='idx_source_job_source_date'),
        ]


class PlatformBenchmark(models.Model):
    """
    Platform-wide benchmark metrics computed periodically.
    Used to show companies how they compare to the platform average.
    """
    metric_name = models.CharField(max_length=100, db_index=True)  # "avg_time_to_hire", "avg_application_rate", etc.
    industry = models.CharField(max_length=150, blank=True, db_index=True)  # Empty = all industries
    value = models.FloatField()
    sample_size = models.PositiveIntegerField(default=0)  # How many data points
    period_start = models.DateField()
    period_end = models.DateField()
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('metric_name', 'industry', 'period_start')
```

### 5.3 API Endpoints

```
GET  /api/v1/intelligence/analytics/funnel/
     → Hiring funnel data for the authenticated company
     → Params: ?period=30d&job_id=123 (optional job filter)
     → Returns: {stages: [{name, count, conversion_rate}], trend: [{date, ...}]}

GET  /api/v1/intelligence/analytics/time-to-hire/
     → Time-to-hire metrics per stage
     → Params: ?period=30d&job_id=123
     → Returns: {metrics: [{stage, avg_hours, median_hours, trend}]}

GET  /api/v1/intelligence/analytics/sources/
     → Source attribution analytics
     → Params: ?period=30d&job_id=123
     → Returns: {sources: [{source, views, applications, conversion_rate}], top_queries: [...]}

GET  /api/v1/intelligence/analytics/talent-pool/
     → Talent pool demographics for the company's applicants
     → Params: ?period=30d&job_id=123
     → Returns: {skills: [{name, count}], experience_levels: [{level, count}], locations: [{loc, count}]}

GET  /api/v1/intelligence/analytics/benchmarks/
     → Platform benchmarks comparison
     → Returns: {metrics: [{name, your_value, platform_avg, industry_avg, percentile}]}

GET  /api/v1/intelligence/analytics/jobs/
     → Per-job performance table
     → Returns: paginated list of jobs with their individual metrics

GET  /api/v1/intelligence/analytics/overview/
     → High-level stats (for dashboard cards at the top)
     → Returns: {total_views, total_applications, active_jobs, avg_match_score, ...}

# Admin-only endpoints
GET  /api/v1/intelligence/analytics/platform/
     → Platform-wide analytics (admin dashboard)
     → Returns: {total_users, total_jobs, total_applications, growth_rates, ...}
```

### 5.4 Celery Tasks

```python
# Periodic: compute daily funnel snapshots (every day at 01:00 UTC)
'intelligence.tasks.compute_daily_funnel_snapshots' → queue='default', schedule=crontab(hour=1, minute=0)

# Periodic: compute platform benchmarks (weekly, Monday 01:30 UTC)
'intelligence.tasks.compute_platform_benchmarks' → queue='default', schedule=crontab(hour=1, minute=30, day_of_week=1)

# Periodic: aggregate weekly/monthly snapshots from daily data (Monday 02:00 UTC)
'intelligence.tasks.aggregate_period_snapshots' → queue='default', schedule=crontab(hour=2, minute=0, day_of_week=1)
```

---

## 6. COMPONENT 4: A/B TESTING FRAMEWORK

### 6.1 Architecture: PostHog Feature Flags + Custom Tracking

Using PostHog's free-tier feature flags (already configured — API key exists in `.env`). Building a thin server-side wrapper + Django middleware + React hook for seamless integration.

```
A/B Testing Flow:

  Server-Side (Django):
    │
    ├─ Middleware: On every request, fetch active feature flags for the user
    │  from PostHog (cached 5 min in Redis to avoid API latency)
    │
    ├─ View Decorator: @experiment('recommendation_weights')
    │  Injects variant into the view context
    │
    └─ Tracking: When a conversion event happens (application, hire, etc.),
       send the event to PostHog with the experiment metadata

  Client-Side (React):
    │
    ├─ useFeatureFlag('recommendation_weights') hook
    │  Reads from PostHog JS client (already installed: posthog-js 1.356)
    │
    ├─ useExperiment('recommendation_weights') hook
    │  Returns variant + tracking helper
    │
    └─ Automatic exposure logging when component renders
```

### 6.2 PostHog Server-Side Client (intelligence/experiments/client.py)

```python
class PostHogClient:
    """
    Server-side PostHog client for feature flag evaluation and event tracking.
    Caches flag evaluations in Redis (5 min TTL) to avoid API latency on every request.
    Falls back gracefully to defaults if PostHog is unreachable.
    """
    - get_feature_flag(flag_key, user_id, default=False) → str | bool
    - get_all_flags(user_id) → dict
    - capture_event(user_id, event_name, properties={})
    - is_feature_enabled(flag_key, user_id) → bool
```

### 6.3 Django Middleware (intelligence/experiments/middleware.py)

```python
class ExperimentMiddleware:
    """
    Attaches active feature flags to every request as `request.feature_flags`.
    Flags are cached per-user in Redis for 5 minutes.
    Only runs for authenticated users.
    """
```

### 6.4 View Decorators (intelligence/experiments/decorators.py)

```python
@experiment('experiment_name', default_variant='control')
def my_view(request):
    variant = request.experiment_variant  # 'control' or 'treatment'
    ...

# Also: a context manager for non-view code
with experiment_context('experiment_name', user_id) as variant:
    if variant == 'treatment':
        ...
```

### 6.5 React Hooks (Frontend)

```javascript
// src/hooks/useExperiment.js
const { variant, isLoading } = useExperiment('recommendation_weights')
// variant: 'control' | 'treatment_a' | 'treatment_b'

// src/hooks/useFeatureFlag.js  
const isEnabled = useFeatureFlag('new_search_ui')
// boolean
```

### 6.6 Initial Experiments to Configure

```
Experiment 1: "recommendation_weights"
  - Control:    content=0.45, collab=0.30, popularity=0.15, freshness=0.10
  - Treatment:  content=0.35, collab=0.40, popularity=0.15, freshness=0.10
  - Metric:     Application rate from recommendation page

Experiment 2: "resume_parser_prompt"
  - Control:    Show "Upload Resume" CTA
  - Treatment:  Show "Auto-fill Profile from Resume (AI-Powered)" CTA
  - Metric:     Resume upload rate

Experiment 3: "match_score_display"
  - Control:    Show percentage (85%)
  - Treatment:  Show label + bar ("Strong Match" with progress bar)
  - Metric:     Application rate from job detail page
```

---

## 7. COMPONENT 5: DATA WAREHOUSE + ETL PIPELINE

### 7.1 Architecture: Analytics Tables + Celery ETL in Neon PostgreSQL

Using your existing Neon PostgreSQL. No external analytics DB needed.

```
ETL Architecture:

  OLTP Tables (live data)           ETL Tasks (Celery)           OLAP Tables (analytics)
  ┌──────────────┐                  ┌──────────────┐              ┌──────────────────────┐
  │ JobPost      │──────────────────│ Daily ETL    │─────────────→│ HiringFunnelSnapshot │
  │ Application  │  extract +       │ (01:00 UTC)  │  load        │ (pre-aggregated)     │
  │ SavedJob     │  transform       │              │              │                      │
  │ User         │                  │ Weekly ETL   │              │ PlatformBenchmark    │
  │ TalentProfile│                  │ (Monday)     │              │ (benchmarks)         │
  │ CompanyProfile│                 │              │              │                      │
  │ SearchAnalytics│                │ Monthly ETL  │              │ SourceAttribution    │
  │ UserInteraction│                │ (1st of mo.) │              │ (source tracking)    │
  │ Notification │                  └──────────────┘              │                      │
  │ Message      │                                                │ DailyPlatformMetrics │
  │ Thread       │                                                │ (admin dashboard)    │
  └──────────────┘                                                └──────────────────────┘
```

### 7.2 Additional Analytics Model

```python
class DailyPlatformMetrics(models.Model):
    """
    Daily platform-wide metrics for admin dashboard and investor reporting.
    One row per day, computed by the nightly ETL task.
    """
    date = models.DateField(unique=True, db_index=True)

    # User metrics
    total_users = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    active_users_1d = models.PositiveIntegerField(default=0)  # DAU
    active_users_7d = models.PositiveIntegerField(default=0)  # WAU
    active_users_30d = models.PositiveIntegerField(default=0) # MAU
    talent_count = models.PositiveIntegerField(default=0)
    company_count = models.PositiveIntegerField(default=0)

    # Job metrics
    total_open_jobs = models.PositiveIntegerField(default=0)
    new_jobs_posted = models.PositiveIntegerField(default=0)
    jobs_closed = models.PositiveIntegerField(default=0)

    # Application metrics
    total_applications = models.PositiveIntegerField(default=0)
    new_applications = models.PositiveIntegerField(default=0)
    offers_extended = models.PositiveIntegerField(default=0)

    # Engagement metrics
    total_messages_sent = models.PositiveIntegerField(default=0)
    total_searches = models.PositiveIntegerField(default=0)
    avg_search_results = models.FloatField(null=True, blank=True)
    total_recommendation_requests = models.PositiveIntegerField(default=0)
    avg_recommendation_ctr = models.FloatField(null=True, blank=True)  # click-through rate

    # Revenue metrics (from Stripe — future integration)
    # mrr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # new_subscriptions = models.PositiveIntegerField(default=0)

    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Daily Platform Metrics'
        verbose_name_plural = 'Daily Platform Metrics'
```

### 7.3 ETL Task Details

```python
# Daily ETL — compute_daily_funnel_snapshots:
#   1. For each company with active jobs:
#      a. Count views_count per job (from JobPost.views_count)
#      b. Count applications grouped by status (pending, reviewing, shortlisted, etc.)
#      c. Compute avg time between status transitions (applied_at → first status change)
#      d. Upsert HiringFunnelSnapshot (date=today, period='daily')
#   2. Also compute aggregate snapshot (job=null) for all company's jobs combined

# Daily ETL — compute_daily_platform_metrics:
#   1. Count users by role, active status
#   2. DAU/WAU/MAU from last_login timestamps
#   3. Count jobs, applications, messages, searches
#   4. Compute recommendation CTR from RecommendationLog + UserInteraction
#   5. Upsert DailyPlatformMetrics

# Weekly ETL — aggregate_period_snapshots:
#   1. Roll up daily HiringFunnelSnapshot → weekly (sum counts, avg times)
#   2. Roll up daily DailyPlatformMetrics → weekly aggregates

# Weekly ETL — compute_platform_benchmarks:
#   1. For each metric (time_to_hire, application_rate, etc.):
#      a. Compute platform-wide average
#      b. Compute per-industry averages
#      c. Upsert PlatformBenchmark
```

---

## 8. FILE MANIFEST

### New Files to Create

```
backend/intelligence/__init__.py
backend/intelligence/apps.py
backend/intelligence/admin.py
backend/intelligence/models.py
backend/intelligence/serializers.py
backend/intelligence/views.py
backend/intelligence/urls.py
backend/intelligence/signals.py
backend/intelligence/tasks.py
backend/intelligence/permissions.py
backend/intelligence/constants.py
backend/intelligence/migrations/__init__.py

backend/intelligence/engine/__init__.py
backend/intelligence/engine/vectorizer.py
backend/intelligence/engine/collaborative.py
backend/intelligence/engine/content_based.py
backend/intelligence/engine/hybrid.py
backend/intelligence/engine/features.py
backend/intelligence/engine/cache.py

backend/intelligence/nlp/__init__.py
backend/intelligence/nlp/parser.py
backend/intelligence/nlp/extractors.py
backend/intelligence/nlp/taxonomy.py
backend/intelligence/nlp/patterns.py
backend/intelligence/nlp/normalizer.py

backend/intelligence/analytics/__init__.py
backend/intelligence/analytics/warehouse.py
backend/intelligence/analytics/aggregators.py
backend/intelligence/analytics/materialized.py
backend/intelligence/analytics/benchmarks.py

backend/intelligence/experiments/__init__.py
backend/intelligence/experiments/client.py
backend/intelligence/experiments/middleware.py
backend/intelligence/experiments/decorators.py
backend/intelligence/experiments/tracking.py

src/hooks/useExperiment.js
src/hooks/useFeatureFlag.js
```

### Existing Files to Modify

```
backend/talentorbit/settings.py
  - Add 'intelligence' to INSTALLED_APPS
  - Add ExperimentMiddleware to MIDDLEWARE
  - Add POSTHOG_API_KEY, POSTHOG_HOST settings (read from .env — already there)
  - Add INTELLIGENCE_* settings block
  - Add new Celery task routes and beat schedules

backend/talentorbit/urls.py
  - Add: path('api/v1/intelligence/', include('intelligence.urls'))

backend/requirements.txt
  - Add: scikit-learn>=1.4.0
  - Add: spacy>=3.7.0
  - Add: posthog>=3.5.0  (server-side SDK — different from posthog-js)
  - Add: numpy>=1.26.0
  - Add: scipy>=1.12.0

backend/jobs/serializers.py
  - Replace get_match_score() in JobPostSerializer to call recommendation engine
  - Replace get_match_score() in JobSearchResultSerializer to call recommendation engine

backend/search/serializers.py
  - Replace get_match_score() in JobSearchResultSerializer to call recommendation engine

backend/accounts/views.py
  - Remove ExtractResumeView class, SKILLS_DB, RESUME_* constants
  - Remove the extract-resume/ URL (moved to intelligence app)

backend/accounts/urls.py
  - Remove extract-resume/ path

backend/jobs/views.py
  - Add UserInteraction tracking on job detail view (view event)
  - Add source attribution tracking on apply view

backend/search/views.py
  - Add UserInteraction tracking on search click
  - Add source attribution for search-originated views

backend/.env
  - Add: POSTHOG_PROJECT_API_KEY (already exists as POSTHOG_API_KEY)
  - This is already configured, no change needed

src/services/api.js
  - Add intelligence service methods (getRecommendations, parseResume, getAnalytics, etc.)

src/store/searchStore.js
  - Add recommendation state management
```

---

## 9. DATABASE MODELS (COMPLETE SCHEMA)

All models in `intelligence/models.py`:

| Model | Purpose | Key Fields |
|---|---|---|
| `SkillTaxonomy` | Canonical skills with aliases | canonical_name, category, aliases (JSON), embedding_vector, usage_count |
| `UserInteraction` | All user-job interactions | user FK, job FK, interaction_type (view/click/save/apply), weight, metadata |
| `RecommendationLog` | Audit trail for recommendations | user FK, recommended_jobs (JSON), algorithm_version, weights_used, latency_ms |
| `ModelArtifact` | Trained ML models (serialized) | name, version, artifact_data (binary), metadata, is_active |
| `ParsedResume` | NLP-parsed resume data | user OneToOne, parsed_skills/experience/education (JSON), confidence, file_hash |
| `HiringFunnelSnapshot` | Pre-aggregated funnel metrics | company FK, job FK, date, views/apps/shortlisted/... counts, avg_time metrics |
| `SourceAttribution` | How users find jobs | job FK, user FK, source (direct/search/recommendation), search_query, converted |
| `PlatformBenchmark` | Platform-wide benchmarks | metric_name, industry, value, sample_size, period_start/end |
| `DailyPlatformMetrics` | Daily admin analytics | date, user counts, job counts, engagement metrics |

---

## 10. API ENDPOINTS (COMPLETE SPECIFICATION)

```
# ── Recommendations ──
GET  /api/v1/intelligence/recommendations/jobs/           → Talent: personalized job recommendations
GET  /api/v1/intelligence/recommendations/talent/          → Company: recommended talent for a job
GET  /api/v1/intelligence/match-score/                     → Detailed match breakdown (job ↔ user)
POST /api/v1/intelligence/interactions/                    → Record user interaction

# ── Resume Parsing ──
POST /api/v1/intelligence/parse-resume/                    → Upload + NLP parse
POST /api/v1/intelligence/parse-resume/apply/              → Apply parsed data to profile
GET  /api/v1/intelligence/parse-resume/                    → Get latest parsed data
GET  /api/v1/intelligence/skills/taxonomy/                 → Skill taxonomy (autocomplete)
GET  /api/v1/intelligence/skills/suggestions/              → Suggested skills based on profile

# ── Company Analytics ──
GET  /api/v1/intelligence/analytics/overview/              → Dashboard overview cards
GET  /api/v1/intelligence/analytics/funnel/                → Hiring funnel (with trend)
GET  /api/v1/intelligence/analytics/time-to-hire/          → Time-to-hire metrics
GET  /api/v1/intelligence/analytics/sources/               → Source attribution
GET  /api/v1/intelligence/analytics/talent-pool/           → Talent pool demographics
GET  /api/v1/intelligence/analytics/benchmarks/            → Platform benchmarks comparison
GET  /api/v1/intelligence/analytics/jobs/                  → Per-job performance table
GET  /api/v1/intelligence/analytics/export/                → Export analytics as CSV/JSON

# ── Admin Analytics ──
GET  /api/v1/intelligence/analytics/platform/              → Platform-wide metrics (admin)
GET  /api/v1/intelligence/analytics/platform/growth/       → Growth trends (admin)
GET  /api/v1/intelligence/analytics/platform/engagement/   → Engagement metrics (admin)

# ── A/B Testing ──
GET  /api/v1/intelligence/experiments/flags/               → Get active feature flags for user
POST /api/v1/intelligence/experiments/track/               → Track conversion event
```

---

## 11. CELERY TASKS (COMPLETE SPECIFICATION)

### New Tasks

| Task Name | Schedule | Queue | Purpose |
|---|---|---|---|
| `intelligence.tasks.retrain_tfidf_vectorizer` | Daily 02:00 UTC | default | Retrain TF-IDF on full skill corpus |
| `intelligence.tasks.rebuild_interaction_matrix` | Daily 02:30 UTC | default | Rebuild collaborative filtering matrix |
| `intelligence.tasks.rebuild_skill_entity_ruler` | Daily 03:00 UTC | default | Update spaCy EntityRuler from taxonomy |
| `intelligence.tasks.update_skill_taxonomy` | Daily 03:30 UTC | default | Update usage counts in SkillTaxonomy |
| `intelligence.tasks.warm_recommendation_cache` | Daily 04:00 UTC | default | Pre-compute recs for active users |
| `intelligence.tasks.discover_new_skills` | Weekly Sun 04:00 | default | Auto-detect new skills from job posts |
| `intelligence.tasks.compute_daily_funnel_snapshots` | Daily 01:00 UTC | default | ETL: funnel metrics |
| `intelligence.tasks.compute_daily_platform_metrics` | Daily 01:15 UTC | default | ETL: platform metrics |
| `intelligence.tasks.compute_platform_benchmarks` | Weekly Mon 01:30 | default | ETL: benchmark metrics |
| `intelligence.tasks.aggregate_period_snapshots` | Weekly Mon 02:00 | default | Roll up daily → weekly/monthly |
| `intelligence.tasks.parse_resume_async` | On-demand | default | Async resume parsing for large files |
| `intelligence.tasks.cleanup_old_recommendation_logs` | Monthly 1st 05:00 | default | Delete rec logs > 90 days |
| `intelligence.tasks.cleanup_old_interactions` | Monthly 1st 05:30 | default | Delete raw interactions > 180 days |

### Beat Schedule Addition

```python
CELERY_BEAT_SCHEDULE.update({
    'retrain-tfidf-vectorizer': {
        'task': 'intelligence.tasks.retrain_tfidf_vectorizer',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'default'},
    },
    'rebuild-interaction-matrix': {
        'task': 'intelligence.tasks.rebuild_interaction_matrix',
        'schedule': crontab(hour=2, minute=30),
        'options': {'queue': 'default'},
    },
    'rebuild-skill-entity-ruler': {
        'task': 'intelligence.tasks.rebuild_skill_entity_ruler',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'default'},
    },
    'update-skill-taxonomy': {
        'task': 'intelligence.tasks.update_skill_taxonomy',
        'schedule': crontab(hour=3, minute=30),
        'options': {'queue': 'default'},
    },
    'warm-recommendation-cache': {
        'task': 'intelligence.tasks.warm_recommendation_cache',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'default'},
    },
    'discover-new-skills': {
        'task': 'intelligence.tasks.discover_new_skills',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),
        'options': {'queue': 'default'},
    },
    'compute-daily-funnel-snapshots': {
        'task': 'intelligence.tasks.compute_daily_funnel_snapshots',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'default'},
    },
    'compute-daily-platform-metrics': {
        'task': 'intelligence.tasks.compute_daily_platform_metrics',
        'schedule': crontab(hour=1, minute=15),
        'options': {'queue': 'default'},
    },
    'compute-platform-benchmarks': {
        'task': 'intelligence.tasks.compute_platform_benchmarks',
        'schedule': crontab(hour=1, minute=30, day_of_week=1),
        'options': {'queue': 'default'},
    },
    'aggregate-period-snapshots': {
        'task': 'intelligence.tasks.aggregate_period_snapshots',
        'schedule': crontab(hour=2, minute=0, day_of_week=1),
        'options': {'queue': 'default'},
    },
    'cleanup-old-recommendation-logs': {
        'task': 'intelligence.tasks.cleanup_old_recommendation_logs',
        'schedule': crontab(hour=5, minute=0, day_of_month=1),
        'options': {'queue': 'default'},
    },
    'cleanup-old-interactions': {
        'task': 'intelligence.tasks.cleanup_old_interactions',
        'schedule': crontab(hour=5, minute=30, day_of_month=1),
        'options': {'queue': 'default'},
    },
})
```

---

## 12. FRONTEND DESIGN REQUIREMENTS

### Pages That Need Design Files From You

I need you to provide designs for these pages/components. For each, I'm describing what currently exists and what the new design needs to show:

---

### PAGE 1: Company Analytics Dashboard (NEW PAGE)

**URL:** `/company/analytics`  
**Current State:** Does not exist. CompanyDashboard currently shows a basic overview.  
**What's Needed:** A full analytics dashboard with:

- **Header section:** Date range picker (7d/30d/90d/custom), Export button
- **KPI Cards row:** Total Views, Total Applications, Active Jobs, Avg Match Score, Avg Time-to-Hire — each with sparkline trend and % change vs. previous period
- **Hiring Funnel Visualization:** Horizontal or vertical funnel showing: Views → Applications → Reviewing → Shortlisted → Interviewing → Offered → Hired, with counts and conversion rates between stages
- **Time-to-Hire Chart:** Bar chart or timeline showing average days at each stage
- **Source Attribution Pie/Donut Chart:** Direct vs. Search vs. Recommendation vs. External
- **Talent Pool Section:** Skills distribution (horizontal bar chart), Experience level distribution (donut), Top locations (bar chart)
- **Platform Benchmarks Section:** Comparison bars (your value vs. platform avg vs. industry avg)
- **Job Performance Table:** Sortable table with columns: Job Title, Status, Views, Applications, Shortlisted, Interviews, Offers, Avg Match Score, Days Active, Health Indicator

**Design Language Notes:** Should follow the existing brutalist design aesthetic with the tape bars, monospace accents, black/white/accent palette. Data visualizations should be clean and minimal — no 3D charts, no gradients.

---

### PAGE 2: Talent "Recommended For You" Section (ENHANCEMENT to UserDashboard or JobBoard)

**URL:** `/dashboard` or `/jobs` (integrated section)  
**Current State:** JobBoard shows a list of all open jobs with basic filters. UserDashboard shows application stats.  
**What's Needed:**

- **"Recommended For You" hero section** at the top of the job board or dashboard
- Shows top 6-8 job cards with:
  - Match score as a prominent badge (e.g., "92% Match")
  - Match breakdown tooltip on hover (Skills: 90%, Experience: 85%, Location: 100%)
  - "Why recommended" explanation text below the card
  - Quick Apply button
- **"Based on your skills"** / **"Similar to jobs you've saved"** / **"Companies like yours"** section labels
- Horizontal scroll or grid layout
- Skeleton loading state while ML inference runs

---

### PAGE 3: Enhanced Resume Upload/Parse Page (ENHANCEMENT to UserProfile)

**URL:** `/profile` (within talent profile editing)  
**Current State:** Simple file upload field for resume in TalentProfileView  
**What's Needed:**

- **Upload zone** with drag-and-drop + file picker
- **Parsing progress indicator** (animated, shows steps: Extracting text → Analyzing skills → Detecting experience → Generating bio)
- **Parsed Results Preview:**
  - Extracted Skills as editable tag chips (user can add/remove before applying)
  - Experience timeline (vertical timeline with company, title, dates)
  - Education cards (degree, institution, year)
  - Generated bio preview with edit capability
  - Confidence indicators per section (green/yellow/red)
- **"Apply to Profile" button** — applies selected parsed data to the actual TalentProfile
- **"Re-parse" button** for re-uploading a different file
- Side-by-side comparison: "Current Profile" vs. "Parsed from Resume"

---

### PAGE 4: Admin Platform Analytics Dashboard (ENHANCEMENT to AdminConsole)

**URL:** `/admin/analytics` (new tab/section within admin console)  
**Current State:** AdminConsole has basic stats: talent_count, company_count, open_jobs, total_applications  
**What's Needed:**

- **KPI Cards:** Total Users (with DAU/WAU/MAU breakdown), Total Jobs, Total Applications, Revenue (placeholder for future)
- **Growth Charts:** New users per day/week (line chart), New jobs per day/week, Applications per day/week
- **Engagement Metrics:** Avg searches per user, Recommendation CTR, Message response rate
- **User Funnel:** Registration → Verification → Profile Completion → First Application/Post
- **Platform Health:** Celery queue sizes, API response times (from Sentry), Error rates

---

### PAGE 5: Skill Suggestions / Taxonomy Browser (NEW COMPONENT)

**URL:** Embedded in profile editing + job posting forms  
**Current State:** Free-text JSON array for skills, no validation or suggestions  
**What's Needed:**

- **Autocomplete input** that searches the SkillTaxonomy
- **Category-grouped skill browser** (expandable accordion: Programming → React, Python, etc.)
- **"Popular skills in your industry"** suggestions
- **"Skills frequently paired with [your current skills]"** suggestions
- Chip/tag display for selected skills with remove button

---

### DESIGN IMPROVEMENTS I RECOMMEND

| Current Component | Issue | Recommended Improvement |
|---|---|---|
| Job cards on JobBoard | match_score shows as plain percentage, easy to miss | Prominent colored badge (green >80%, yellow 50-80%, red <50%) with ring/progress indicator |
| Company Dashboard | Very basic, just job list | Add analytics overview cards at the top (views today, pending reviews, etc.) |
| Search results | No indication of personalization | Add "Recommended" badge on results that the ML engine boosted |
| Notification bell | No categorization in UI | Add category-based grouping or filtering (Applications, Messages, Recommendations, System) |
| Settings page | No experiment/feature preview | Consider adding "Beta features" toggle section (powered by feature flags) |

---

## 13. DEPENDENCIES

### New Python Packages

```
scikit-learn>=1.4.0         # TF-IDF vectorizer, cosine similarity, ML utilities
spacy>=3.7.0                # NLP pipeline (NER, tokenization, POS tagging)
posthog>=3.5.0              # Server-side PostHog SDK for feature flags + events
numpy>=1.26.0               # Numerical computing (vectors, matrices)
scipy>=1.12.0               # Sparse matrices for collaborative filtering
```

### spaCy Model Download (Post-Install)

```bash
python -m spacy download en_core_web_sm
```

This is the small English model (~12MB). Free. Includes tokenizer, tagger, parser, NER, word vectors. The EntityRuler for skills is added programmatically from `SkillTaxonomy`.

### No New Frontend Packages Needed

- `posthog-js` is already installed (v1.356)
- `recharts` or similar for charts — **you'll need to confirm if you want me to add a charting library, OR if your design will include chart components that you'll provide**
- Currently no charting library is in `package.json`

**Question for you:** For the analytics charts, should I add `recharts` (most popular React charting lib, free, 2.2MB gzipped) or do you prefer a different one? Or will your designs include a specific chart library preference?

---

## 14. MIGRATION & DEPLOYMENT

### Step-by-Step Execution Order

```
1. Install new Python packages
   pip install scikit-learn spacy posthog numpy scipy
   python -m spacy download en_core_web_sm

2. Create intelligence app directory structure

3. Create all model files

4. Generate migrations
   python manage.py makemigrations intelligence

5. Run migrations
   python manage.py migrate

6. Seed SkillTaxonomy with initial data (via management command or data migration)
   - ~500 canonical skills across categories
   - Programming, Data Science, Design, Marketing, Management, etc.

7. Update settings.py (INSTALLED_APPS, MIDDLEWARE, CELERY_BEAT_SCHEDULE)

8. Update urls.py (add intelligence routes)

9. Modify existing files (serializers, views, accounts/views.py cleanup)

10. Create frontend hooks and service methods

11. Run the full test suite

12. Deploy
```

### Data Migration: Seed SkillTaxonomy

A data migration that seeds ~500 skills across categories. Example subset:

```python
INITIAL_SKILLS = [
    {"canonical_name": "python", "category": "Programming", "aliases": ["Python", "Python3", "python3"]},
    {"canonical_name": "javascript", "category": "Programming", "aliases": ["JavaScript", "JS", "js", "Javascript"]},
    {"canonical_name": "react", "category": "Frontend", "aliases": ["React", "React.js", "ReactJS", "react.js"]},
    {"canonical_name": "django", "category": "Backend", "aliases": ["Django", "django-rest-framework", "DRF"]},
    {"canonical_name": "machine-learning", "category": "Data Science", "aliases": ["Machine Learning", "ML", "machine learning"]},
    # ... ~500 more
]
```

### Environment Variables (No Changes Needed)

All required env vars already exist:
- `POSTHOG_API_KEY` → used for server-side PostHog SDK
- `POSTHOG_HOST` → PostHog host URL
- `UPSTASH_REDIS_URL` → Redis for caching ML artifacts + recommendations
- `DATABASE_URL` → Neon PostgreSQL for all new tables

---

## 15. QUALITY GUARANTEES

### What Makes This Enterprise-Grade, Not MVP

1. **Real-time ML inference** with sub-100ms latency via aggressive Redis caching + pre-computed feature vectors
2. **Hybrid recommendation engine** combining 4 signals (content, collaborative, popularity, freshness) — same architecture as LinkedIn, Netflix, Spotify
3. **Full NLP pipeline** with spaCy NER + custom EntityRuler + section-aware parsing — not regex hacks
4. **Canonical skill taxonomy** with 500+ skills, alias normalization, and auto-discovery of new skills
5. **Pre-aggregated analytics** via ETL — O(1) dashboard queries regardless of data size
6. **A/B testing built into the recommendation engine** — weights are experimentable from day 1
7. **Audit logging** for all recommendations (RecommendationLog) enabling offline evaluation and model comparison
8. **Cold-start handling** for new users (fallback to content-based) and new jobs (similarity to popular jobs)
9. **Diversity injection** in recommendations (no more than 3 from same company)
10. **Explainability** — every recommendation comes with a human-readable "why" explanation
11. **Source attribution** tracking — companies can see exactly where their applicants came from
12. **Platform benchmarks** — companies compare their performance against industry averages
13. **Graceful degradation** — if PostHog is down, feature flags return defaults; if ML model is stale, still works with cached version
14. **Dead-letter queue integration** — all tasks use the existing `BaseTaskWithDLQ` pattern
15. **Cache invalidation** — recommendations cache busted on new application, save, or profile update

---

## READY TO BUILD

Clear context, paste this plan, and say "Execute Phase 5 — start with Component [1/2/3/4/5]" and I'll write every line of enterprise-grade code.

**What I need from you before starting:**
1. ✅ Confirm this plan looks good
2. 📐 Provide design files for the 5 pages described in Section 12
3. 📊 Tell me which charting library you prefer for analytics (I recommend `recharts`)
4. 🚀 Tell me which component to start with (I recommend: Component 2 → 1 → 4 → 3 → 5, because the skill taxonomy from resume parsing feeds the recommendation engine)
