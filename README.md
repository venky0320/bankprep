# BankPrep

A Django web app for practising Indian banking exams (IBPS PO, IBPS Clerk, SBI PO, SBI Clerk, IBPS RRB).
It has a syllabus tracker with subtopics, topic and subtopic practice, mock tests, study notes and a wrong-answer review.

## Set up (Windows PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Create your private settings file (it is never uploaded to Git)
Copy-Item .env.example .env
# Then open .env and replace the secret key with a new one. Make a key with:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

python manage.py migrate
python manage.py createsuperuser

# Load the syllabus, starter questions and notes, then the subtopics
python manage.py import_data
python manage.py load_subtopics
python manage.py import_questions

python manage.py runserver
```

Open http://127.0.0.1:8000/ . The admin is at http://127.0.0.1:8000/admin/ .

The project also runs without a `.env` file on your own computer, using a non-secret development key.
Debug mode turns off only when `DJANGO_DEBUG=False`, and then a real `DJANGO_SECRET_KEY` is required.

## Useful commands

| Command | What it does |
|---|---|
| `python manage.py audit_syllabus` | Checks the 4 subjects and 48 topics in the database (read-only) |
| `python manage.py list_topics` | Prints topic names |
| `python manage.py list_subtopics` | Prints topics with their subtopics |
| `python manage.py load_subtopics` | Loads `data/subtopics.json` (safe to repeat) |
| `python manage.py import_questions` | Loads `data/questions.csv` |

## Project layout

- `config/` Django settings and root URLs
- `prep/` the app: models, views, templates, management commands
- `data/` syllabus, subtopics, questions and notes as files
- `media/` uploaded PDFs (not in Git)

## Not in this repository

The database (`db.sqlite3`), the virtual environment, uploaded files and any `.env` file are kept out of Git on purpose.