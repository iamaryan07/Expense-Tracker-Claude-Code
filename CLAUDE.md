# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Spendly** is an educational expense tracking web application built with Flask. It's structured as a step-by-step learning project where students implement features incrementally (Steps 1-9). The project covers fundamental web development concepts including database setup, user authentication, CRUD operations, and dynamic UI interactions.

## Architecture

### Directory Structure
- **app.py** — Main Flask application with route definitions
- **database/db.py** — Database module (students implement in Step 1)
- **templates/** — Jinja2 HTML templates with base.html as the layout template
- **static/css/style.css** — Styling (pre-built, uses DM Sans and DM Serif Display fonts)
- **static/js/main.js** — Client-side JavaScript
- **.venv/** — Python virtual environment

### Core Components

**Flask Application (app.py)**
- Routes are organized into sections: implemented routes (landing, register, login) and placeholder routes for student implementation
- Uses render_template for server-side rendering
- Runs on port 5001 with debug mode enabled
- Placeholder routes currently return text placeholders; students replace these with actual template renders and logic

**Database Module (database/db.py)**
- Students implement three functions: `get_db()`, `init_db()`, and `seed_db()`
- Should use SQLite with row_factory and foreign keys enabled
- Must use CREATE TABLE IF NOT EXISTS pattern
- Database file: `expense_tracker.db` (git-ignored)

**Templates (Jinja2)**
- base.html provides site layout with navbar, main content block, and footer
- Child templates (landing.html, register.html, login.html) extend base.html
- Navigation links use url_for() for routing
- Branding: "Spendly" with rupee-focused messaging ("Track every rupee. Own your finances.")

## Running the Application

### Setup
```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install dependencies (if needed)
pip install -r requirements.txt
```

### Run the Development Server
```powershell
python app.py
```
The app starts on `http://localhost:5001` in debug mode with hot-reload.

### Running Tests
```powershell
# Run all tests
pytest

# Run a specific test file
pytest tests/test_auth.py

# Run tests with verbose output
pytest -v

# Run a single test function
pytest tests/test_auth.py::test_login -v
```

## Key Implementation Details

### Step-by-Step Structure
The app has 9 steps, with routes categorized as:
- **Implemented**: `/`, `/register`, `/login` — render static templates
- **Placeholder (Steps 3-9)**:
  - Step 3: `/logout` — session management
  - Step 4: `/profile` — user profile page
  - Step 7: `/expenses/add` — POST form to create expense
  - Step 8: `/expenses/<id>/edit` — PATCH/PUT to update expense
  - Step 9: `/expenses/<id>/delete` — DELETE expense

When implementing placeholder routes:
1. Replace the text return with `render_template()` call
2. Create/update the corresponding template file
3. Implement backend logic (database queries, validation, etc.)
4. Add tests for new functionality

### Database Design Patterns
Students will implement a schema including at least:
- Users table (email, password hash, profile info)
- Expenses table (amount, category, date, user_id, description)
- Categories table (optional but recommended)

Use foreign keys, NOT NULL constraints, and proper indexing where appropriate.

### Template Best Practices
- All templates extend base.html
- Use url_for() for internal links (enables routing flexibility)
- Follow the existing DM Sans/DM Serif Display font usage
- Navbar and footer are inherited from base.html
- Form templates should include CSRF protection when implemented

## Dependencies

- **flask==3.1.3** — Web framework
- **werkzeug==3.1.6** — WSGI utilities (Flask dependency, handles middleware/routing)
- **pytest==8.3.5** — Testing framework
- **pytest-flask==1.3.0** — Flask testing fixtures

## Notes for Implementation

- Database should use SQLite (no ORM required at this stage; raw SQL is appropriate)
- Password storage: students will learn to use werkzeug.security.generate_password_hash
- Session management: Flask sessions (set app.secret_key)
- Dates in expenses: store as ISO format (YYYY-MM-DD) or Unix timestamp
- Category handling: can be hardcoded list or database-backed (recommended)
- No external APIs or authentication libraries required for basic steps
