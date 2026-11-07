# Contributing to Railway Passenger Help Desk

Thank you for your interest in contributing to the **Railway Passenger Help Desk** project. This project is built as part of the GenAI Nexus Fellowship (Module 2 Capstone).

To maintain code quality, reproducibility, and security, all contributors must adhere to the guidelines outlined below.

---

## 1. Golden Security Rules

- **NEVER commit secrets**: API keys, credentials, or private configuration files (`.env`, `.env.local`) must never be added to git. Use `.env.example` as a template.
- **NEVER commit the raw dataset**: The contents of `rail_capstone_pack/`, SQLite `.db` binaries, and `rail_capstone_pack.zip` must remain local. They are strictly excluded by `.gitignore`.
- **Read-Only Database Enforcement**: Never bypass the read-only SQLite URI mode or authorizer callbacks.

---

## 2. Environment Setup

1. Fork or clone the repository:
   ```powershell
   git clone https://github.com/aaxonxn/railway-dummy.git
   cd railway-dummy
   ```
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. Configure `.env` from template:
   ```powershell
   Copy-Item .env.example .env
   # Add your GEMINI_API_KEY to .env
   ```
5. Extract the supplied dataset into `rail_capstone_pack/` and build the retrieval index:
   ```powershell
   python build_index.py --force
   ```

---

## 3. Branching and Workflow

- The main branch is `main`.
- All development work should occur on a dedicated feature or bugfix branch:
  ```powershell
  git checkout -b feature/improved-chunking
  ```
- Keep changes atomic, focused, and well-tested.

---

## 4. Commit Conventions

Follow conventional commit formats:
- `feat: add hybrid reciprocal rank fusion`
- `fix: resolve OCR pixmap conversion on Windows`
- `test: add unit tests for SQLite read-only enforcement`
- `docs: update DEMO_GUIDE with 10-minute presentation flow`
- `refactor: optimize table chunk extraction`

---

## 5. Mandatory Verification Before Submitting PRs

Before submitting a Pull Request, you must verify the following locally:

1. **All automated tests pass**:
   ```powershell
   pytest -v
   ```
2. **Retrieval benchmarks maintain 100% Hit@1**:
   ```powershell
   python eval/evaluate.py --retrieval-only
   ```
3. **Index integrity is preserved**:
   ```powershell
   python build_index.py --check
   ```
4. **Git status inspection**:
   ```powershell
   git status
   ```
   Ensure no `.env`, database binaries, or temporary test artifacts are staged.

---

## 6. Code Style & Architecture

- Maintain strict separation of concerns across `helpdesk/` modules:
  - `ingest.py`: Multi-format parsing (PyMuPDF, BeautifulSoup).
  - `ocr.py`: Tesseract OCR handling.
  - `search.py`: Hybrid search index management.
  - `sql.py`: Timetable SQL execution and validation.
  - `routing.py`: Question classification.
  - `citations.py`: Citation validation and deduplication.
  - `pipeline.py`: Public `ask()` interface adhering to the 4-key contract.
- Preserve docstrings and type annotations.

