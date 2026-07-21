# Stage 2 — Authentication

## Goal
Let a person create an account and log in/out securely. No roles or
organizations yet — just "does this login work and is the session safe."

## Prerequisites
Stage 1 (running app + DB connection) must be complete.

## Features to build
- Registration form: full name, email, password (+ confirm password).
- Passwords are hashed before storage — never stored in plain text.
- Login form: email + password, with a generic error message on failure (never reveal whether the email exists or the password was wrong — say "Invalid email or password" either way).
- Logout (must be a POST request, not a plain link, to avoid CSRF logout tricks).
- Session-based auth: once logged in, the user stays logged in across pages until logout or session expiry.
- Basic profile page showing the logged-in user's name and email.
- A `login_required` mechanism: any page that needs a logged-in user redirects to the login page if there isn't one.

## Frontend — Design & Layout

**Login page** (`/login`):
- Centered card on a plain background, app logo/name above it.
- Fields: Email, Password. One primary "Log In" button.
- Link below the form: "Don't have an account? Register."
- Flash message area above the form for errors ("Invalid email or password").

**Register page** (`/register`):
- Same centered-card layout as login.
- Fields: Full Name, Email, Password, Confirm Password.
- Client-side check that password and confirm-password match before submit (server must re-validate too).
- Link below the form: "Already have an account? Log in."

**Base layout** (used by every page from here on):
- Top header bar: app name/logo on the left, and on the right — when logged in — the user's name/avatar with a dropdown containing "Profile" and "Log Out".
- When logged out, the header just shows Login/Register links.
- Establish the shared color palette and typography now (this becomes the visual foundation for every later stage): pick a primary accent color, neutral grays for backgrounds/borders, and a monospace or clean sans-serif for the UI font.

## Backend — Data Model & API

**Table: `users`**
| Column | Type | Notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| full_name | VARCHAR(150) | |
| email | VARCHAR(150) | UNIQUE, NOT NULL |
| password_hash | VARCHAR(255) | NOT NULL |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP |

**Routes:**
| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/register` | Show form (GET) / create account (POST) |
| GET/POST | `/login` | Show form (GET) / authenticate + start session (POST) |
| POST | `/logout` | Clear session |
| GET | `/profile` | Show logged-in user's info (requires login) |

**Session data to store on login:** `user_id`, `full_name` (at minimum — `organization_id` and `role` get added in Stage 3).

## Definition of Done
- [ ] Can register a new account and immediately see it hashed (not plaintext) in the `users` table.
- [ ] Can log in with correct credentials and get redirected to a landing/dashboard page.
- [ ] Wrong password shows a generic error, not "user not found" vs "wrong password".
- [ ] Visiting a `login_required` page while logged out redirects to `/login`.
- [ ] Logging out and pressing the browser back button does not show protected content.
- [ ] Session cookie is HttpOnly and SameSite=Lax at minimum.
