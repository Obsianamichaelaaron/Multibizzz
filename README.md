# Multibiz - Python & Django Web Platform

Welcome to the **Multibiz** Intelligent Career & Talent Management Platform, successfully migrated from legacy PHP to modern **Python & Django Framework**.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- Dependencies: `django`, `djangorestframework`, `pypdf`, `python-docx`, `scikit-learn`, `pandas`, `whitenoise`

### 2. Run Database Migrations & Seeder (Already Configured)
```bash
python manage.py migrate
python manage.py seed_multibiz_data
```

### 3. Start Development Server
```bash
python manage.py runserver
```
Visit the platform in your browser at: **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 🔑 Default Login Credentials

| Role | Email | Password | Dashboard Access |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin@gmail.com` | `admin123` | `/audit/dashboard/` & `/admin-portal/cms/` |
| **Employer** | `employer@gmail.com` | `employer123` | `/applications/employer/dashboard/` |
| **Jobseeker / Applicant** | `jobseeker@gmail.com` | `jobseeker123` | `/applications/applicant/dashboard/` |

---

## 📁 Architecture & Apps

- **`accounts/`**: Custom user authentication supporting 3 roles (`applicant`, `employer`, `admin`), profile editors, role decorators (`@applicant_required`, `@employer_required`, `@admin_required`).
- **`core/`**: Landing page, About, Services, Solutions, Public Inquiries inbox, CMS editor for Hero slides, Brands, and Testimonials.
- **`jobs/`**: Live job board, skills & qualification taxonomy, search & filters, bookmarking/saved jobs, employer job posting CRUD.
- **`applications/`**: Job application pipeline, ML ranking (`excellent`, `good`, `average`, `poor`), candidate review dossier, status history remarks timeline, interview scheduler.
- **`chatbot/`**: Interactive AI career guidance questionnaire, suitability scoring, dynamic job & learning path recommendations.
- **`messaging/`**: Direct chat messaging center with unread badges, conversation threads, floating chat widget, and notifications.
- **`audit/`**: Security & administrative audit trail logging and analytics reporting.
- **`ml_engine/`**: Automated resume parser (PDF/DOCX) using `pypdf` & `python-docx`, multi-factor TF-IDF & skill matching engine, employability calculator.

---

## 🧪 Verification & Testing
Run automated test suite:
```bash
python test_migration.py
```

## Deploy to PythonAnywhere

The project uses `multibiz_project.wsgi:application` and WhiteNoise for static
files. In a PythonAnywhere Bash console, run:

```bash
cd ~
git clone <your-repository-url> Multibiz
cd Multibiz
mkvirtualenv --python=/usr/bin/python3.10 multibiz-env
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

In the PythonAnywhere **Web** tab, create a web app using the existing virtual
environment and set the WSGI file to:
`/home/<pythonanywhere-username>/Multibiz/multibiz_project/wsgi.py`.
Set these environment variables in the WSGI file before `get_wsgi_application()`
or in the account environment:

```text
SECRET_KEY=<long-random-secret>
DEBUG=False
ALLOWED_HOSTS=<pythonanywhere-username>.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://<pythonanywhere-username>.pythonanywhere.com
SITE_URL=https://<pythonanywhere-username>.pythonanywhere.com/
```

Add these static mappings in the Web tab:

| URL | Directory |
| --- | --- |
| `/static/` | `/home/<pythonanywhere-username>/Multibiz/staticfiles` |
| `/media/` | `/home/<pythonanywhere-username>/Multibiz/media` |

Reload the web app after saving the WSGI file and mappings. The SQLite database
and uploaded media live on the PythonAnywhere filesystem, so back them up
regularly. Google Drive and SMTP credentials should be supplied as environment
variables rather than committed JSON files.

## Deploy to Render

The repository includes [render.yaml](render.yaml), which creates a Django web
service and a PostgreSQL database. Push this repository to GitHub, then in
Render select **New > Blueprint** and choose the repository. Render will use
the blueprint to install dependencies, collect static files, run migrations,
and start Gunicorn.

After deployment, set `CSRF_TRUSTED_ORIGINS` and `SITE_URL` to the actual
Render service URL if the service name is changed. Add SMTP and Google Drive
credentials as Render environment variables when those features are needed.

Render's standard filesystem is ephemeral. Uploaded resumes, profile pictures,
and company logos need external object storage or a paid persistent disk.
