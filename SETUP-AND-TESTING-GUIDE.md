# Setup & Testing Guide

## What you need before you start

1. **Python 3.13 or newer.**
   Check if you already have it by opening a terminal (Command Prompt or
   PowerShell on Windows, Terminal on Mac/Linux) and typing:
   ```
   python --version
   ```
   If that fails or shows an older version, download and install Python
   from [python.org/downloads](https://www.python.org/downloads/).
   On Windows, tick **"Add Python to PATH"** during installation - this is
   the single most common reason `python` isn't recognized afterwards.

2. **MySQL Server, version 8 or newer, installed and running.**
   This app stores all its data in MySQL - nothing works without it. If
   you don't already have MySQL, the easiest options are:
   - **MySQL Installer** (Windows) - [dev.mysql.com/downloads/installer](https://dev.mysql.com/downloads/installer/)
   - **XAMPP** or **Laragon** (Windows) - bundle MySQL with a simple on/off switch
   - **MySQL Workbench** - a free GUI to view your database, install alongside whichever of the above you pick

   During installation, MySQL will ask you to set a **root password** -
   remember what you choose, you'll need it in Step 4.

3. **Git** (if you'll clone the repo) **or an unzip tool** (if you received
   a zip file) - see Step 1 for both options. Either way, land the project
   in a folder with no spaces or special characters in the path if
   possible (e.g. `C:\BugTracker` rather than `C:\My Projects\Bug Tracker!`).

---

## Step 1 - Get the project onto your computer and open a terminal in it

**Option A - Clone the GitHub repo:**
```powershell
git clone https://github.com/shiva1021-crypto/Bug-Tracker.git
cd Bug-Tracker
```

**Option B - Unzip a zip file:**
Extract the zip, then open a terminal and navigate into the extracted
folder. For example, on Windows PowerShell:
```powershell
cd C:\BugTracker
```

Every command below assumes you're standing in this folder (the one that
contains `app.py`, `requirements.txt`, `README.md` and so on).

---

## Step 2 - Create a virtual environment and install dependencies

A virtual environment keeps this project's Python packages separate from
anything else on your computer. It is **not included in the project
files** (zip or clone) - you create a fresh one yourself, every time you
set this project up on a new machine.

```powershell
# Create the virtual environment (only needs to be done once)
python -m venv .venv

# Activate it (do this every time you open a new terminal for this project)
.venv\Scripts\activate

# macOS/Linux instead: source .venv/bin/activate

# Install everything the project needs
pip install -r requirements.txt
```

If activation worked, you'll see `(.venv)` at the start of your terminal
prompt. If `pip install` fails with a permissions error, make sure you
activated the virtual environment first (the line above) rather than
installing into your system-wide Python.

---

## Step 3 - Create your `.env` configuration file

The project needs a file named `.env` in the project root that tells it
how to connect to your MySQL server. This file is **never included in a
zip or in git** on purpose (it can contain passwords), so you must create
your own copy.

```powershell
copy .env.example .env
notepad .env
```
(macOS/Linux: `cp .env.example .env` and open it in any text editor.)

Inside `.env`, find these lines and change them to match **your own**
MySQL installation:

```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=bug_tracker_db
```

- `DB_HOST` - leave as `127.0.0.1` if MySQL is running on the same
  computer (the normal case).
- `DB_PORT` - leave as `3306` unless you specifically configured MySQL to
  use a different port.
- `DB_USER` - the MySQL username you log in with (often `root`).
- `DB_PASSWORD` - the password for that MySQL user. **This is the field
  people most often forget to fill in** - if MySQL has a root password set
  (it usually does) and you leave this blank, every connection will fail.
- `DB_NAME` - leave as `bug_tracker_db`; the setup scripts in Step 5 will
  create this database for you, it doesn't need to exist yet.

Everything else in `.env` already has a sensible default for local
testing and can be left as-is.

Save the file and close the editor.

---

## Step 4 - Confirm MySQL is actually reachable

Before creating anything, check the connection:
```powershell
python -m scripts.check_db
```

**If you see "MySQL is reachable"** - great, move on to Step 5.

**If you see "MySQL is NOT reachable"**, it's one of these, in order of
likelihood:

| Message contains | Likely cause | Fix |
|---|---|---|
| `Can't connect` / `2003` | MySQL isn't running | Start it (MySQL Workbench, MySQL80 in Windows Services, or XAMPP/Laragon's control panel) |
| `Access denied` | Wrong `DB_USER` / `DB_PASSWORD` in `.env` | Re-check the password you set during MySQL installation |
| `Unknown MySQL server host` | Wrong `DB_HOST` | Should be `127.0.0.1` for a local install |
| Connection just hangs / times out | Wrong `DB_PORT`, or a firewall blocking it | Confirm MySQL's real port (3306 by default) |

Re-run `python -m scripts.check_db` after each fix until it succeeds.

---

## Step 5 - Create the database and its tables

Once Step 4 succeeds:
```powershell
python -m scripts.create_db
python -m scripts.create_tables
```
The first command creates an empty `bug_tracker_db` database. The second
creates every table the app needs inside it. Both print what they did as
they go - you should see no red/error text.

`create_tables` is safe to re-run any time (it only adds what's missing),
so don't worry about running it twice by accident.

---

## Step 6 - Load demo data (for testing)

This step fills the database with a realistic demo organization - users
for every role, two projects, sprints and about twenty issues - so you
have something real to click through immediately.

```powershell
python -m scripts.seed_dummy_data
```

At the end it prints a list of login emails and a shared password. Keep
that output visible, or just use the table below (it's the same data):

**Organization:** Nimbus Robotics
**Password for every account below:** `DummyPass123!`

| Email | Role | Name |
|---|---|---|
| admin@nimbus.test | Admin | Ava Admin |
| pm@nimbus.test | Project Manager | Priya Patel |
| dev1@nimbus.test | Developer | Derek Chen |
| dev2@nimbus.test | Developer | Sofia Alvarez |
| tester1@nimbus.test | Tester | Tomas Reyes |
| tester2@nimbus.test | Tester | Grace Kim |

**Projects created:** `WEB` (Web Platform) and `MOB` (Mobile App), each
with its own sprints, versions and a spread of issues in every status,
type and priority.

**Important:** this script refuses to run a second time (to avoid
duplicating data). If you ever want a completely fresh copy, either delete
the "Nimbus Robotics" organization's data yourself, or drop and recreate
the database (repeat Steps 5 and 6).

---

## Step 7 - Run the app

```powershell
python run.py
```
Leave this terminal window open - it's the running server. Open a web
browser and go to:
```
http://127.0.0.1:5000
```
You should see the Bug Tracker landing page. If you instead see a
"MySQL is not reachable" page, go back to Step 4 - the app itself will
tell you the exact same fix checklist.

To stop the server, click into that terminal and press `Ctrl+C`.

---

## Step 8 - Log in and look around

Log in with `admin@nimbus.test` / `DummyPass123!` (or any account from the
table above). You should land on the **Dashboard** with widgets already
showing real numbers, because of the demo data you loaded in Step 6.

---

## Testing checklist - walking through every feature

Use this section to confirm each part of the app actually works. Do these
roughly in order; later steps build on earlier ones. Unless noted, log in
as `admin@nimbus.test`.

### 1. Accounts & organizations
- [ ] Log out (top-right menu), then **Register** a brand-new account with
      a **new** organization name. Confirm you land on the Dashboard
      immediately as that org's Admin, with a default project already
      there.
- [ ] Log out, then register again using **the same** organization name
      you just used. Confirm you get a "pending approval" message instead
      of being logged in.
- [ ] Log back in as that org's Admin → **Admin → Users** and approve or
      reject the pending request you just created.

### 2. Projects
- [ ] Log in as `admin@nimbus.test`. Go to **Projects** - you should see
      `WEB` and `MOB` from the seed data.
- [ ] Create a new project with a 2–6 letter key (e.g. `QA`).
- [ ] Open a project's **Custom Fields** page and add one (e.g. a
      "Environment" dropdown field with options `Staging`/`Production`) -
      the seed data does not create any custom fields, so this is the only
      way to see that feature in action.

### 3. Issues
- [ ] Go to **Issues**, open any seeded issue, confirm its details,
      comments and history are visible.
- [ ] Click **+ Create Issue**, create a new Bug or Task in the `WEB`
      project. Confirm it gets a key like `WEB-21`.
- [ ] Edit that issue (change priority, add labels, upload a screenshot).
- [ ] Try creating an Epic, then a Story underneath it (parent/child) and
      confirm the hierarchy shows correctly on the Epic's detail page.

### 4. Workflow & status
- [ ] Log in as one of the developers (`dev1@nimbus.test`). Open an issue
      assigned to that developer and change its status.
- [ ] Try to change the status of an issue **not** assigned to that
      developer - it should be blocked.
- [ ] As `admin@nimbus.test`, assign an unassigned "To Do" issue to a
      developer and confirm it automatically moves to "In Progress."
- [ ] Add a comment on an issue and click "Watch" on another.

### 5. Kanban Board
- [ ] Go to **Board**, switch between the `WEB` and `MOB` projects using
      the project selector.
- [ ] Drag a card to a different column (logged in as the assignee or as
      Admin). Confirm the status actually changed on the issue's detail
      page afterward.
- [ ] Try the "Group by" dropdown (Assignee / Priority / Issue Type).

### 6. Backlog & Sprints
- [ ] Go to **Backlog** for the `WEB` project - you should see an active
      sprint with a burndown chart, plus unsprinted issues below it.
- [ ] Create a new sprint, then drag/assign a backlog issue into it.
- [ ] As Admin or PM, start or close a sprint.

### 7. Automation Rules
- [ ] Go to **Automation**. The seed data does not create any rules, so
      create one yourself - e.g. trigger "Status Changed," action "Add
      Comment," text `{issue_key} moved to {status}`.
- [ ] Change an issue's status to trigger that condition, then check the
      issue's comments for the automated comment.

### 8. Releases (Versions)
- [ ] Go to **Releases** - confirm both projects show their seeded
      versions with issue counts.
- [ ] Create a new version, then release or archive one.

### 9. Reports & Dashboard (Admin/PM only)
- [ ] Go to **Dashboard**, click **+ Add Widget**, add one of each widget
      type, confirm it appears with real data, then remove it.
- [ ] Go to **Reports**, apply a few filters, confirm the charts and table
      update. Click **Export CSV** and open the downloaded file. Click
      **Print** and confirm a clean, sidebar-free print preview appears.
- [ ] Log in as a Tester or Developer and confirm **Reports** is not
      accessible to them (it should redirect away).

### 10. Multi-tenancy (data isolation)
- [ ] Log in as the Admin of the brand-new organization you created in
      Test 1. Confirm you see **none** of Nimbus Robotics' projects,
      issues, or users - a completely empty workspace of your own.

If every box above works the way it's described, the setup is correct and
every stage of the app is functioning.

---

## Troubleshooting

**"ModuleNotFoundError" when running `python run.py`**
You forgot to activate the virtual environment, or `pip install -r
requirements.txt` didn't finish. Re-run Step 2.

**Everything was working, then suddenly every page shows a database
error**
MySQL was stopped (e.g. computer restarted, or XAMPP/Laragon was closed).
Start MySQL again and refresh the page - no other fix needed.

**"Address already in use" / port 5000 busy**
Something else is already using port 5000 (maybe a previous copy of this
app still running). Close that other terminal window, or stop the process
using that port, then try `python run.py` again.

**Forgot the demo password**
It's `DummyPass123!` for every seeded account - see the table in Step 6.

**Want a completely clean slate**
Stop the app, drop the `bug_tracker_db` database in MySQL Workbench (or
`DROP DATABASE bug_tracker_db;` in a MySQL client), then repeat Steps 5
and 6.
