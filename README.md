# SG Fluid Technologies — Company Website + Installer Verification Portal

One Flask app serving the SG Fluid Technologies marketing site (home page,
engineering inquiry form, thank-you page) together with the Lokring installer
certification verification tool and its admin panel.

**Brand positioning:** SG Fluid Technologies Pte Ltd is the operating company
(shown as the major name throughout); Lokring Asia is the supplier/product
line it distributes (shown as a smaller "Distributor of Lokring Asia" credit).

**No VS Code extensions required.** Everything below uses VS Code's built-in terminal
and task runner — you do not need the Python extension (or any extension) to set up
or run this app.

## Pages

| Route | What it is |
|---|---|
| `/` | Marketing homepage (hero, value props, contact form) |
| `/thanks` | Shown after the contact form is submitted |
| `/verify` | Public installer certification lookup |
| `/admin/login` | Admin sign-in |
| `/admin` | Admin dashboard (add/edit/delete installers) |

## Fastest way to run this (recommended)

You still need Python itself installed on your computer (there's no way around that
for a Flask app — get it from python.org if you don't have it), but everything after
that is one click inside VS Code, with zero extensions.

**First time only:**
1. Open the `installer_portal` folder in VS Code (`File > Open Folder...`).
2. Top menu: `Terminal > Run Task... > 1. Setup (run once)`.
   This creates a virtual environment and installs Flask automatically — no typing required.

   (Alternative, without opening VS Code at all: double-click `setup.bat` in Windows Explorer, or run `bash setup.sh` on Mac/Linux.)

**Every time you want to run it:**
- Press `Ctrl+Shift+B` (VS Code's built-in "Run Build Task" shortcut — works with zero extensions installed).
- Or double-click `run.bat` (Windows) / run `./run.sh` (Mac/Linux) directly, outside VS Code entirely.

Once you see `Running on http://127.0.0.1:5000` in the terminal, open that link in your browser.
To stop the server, click the trash/stop icon on the terminal panel, or press `Ctrl+C`.

That's it — no manual `venv`, `activate`, `pip install`, interpreter selection, or extensions needed.

---

## Optional: debugging with F5 (requires the Python extension)

If you later install Microsoft's Python extension and want to set breakpoints and step
through code, `.vscode/launch.json` is already configured — just press F5. This is
entirely optional; the workflow above doesn't need it.

---

## Project structure

```
installer_portal/
├── .vscode/
│   ├── tasks.json        # "Setup" and "Run App" tasks (no extension needed)
│   ├── launch.json        # Optional F5 debug config (needs Python extension)
│   └── settings.json
├── static/
│   ├── favicon.ico, favicon-16x16.png, favicon-32x32.png, apple-touch-icon.png
│   ├── site.webmanifest
│   └── lokring-logo.png   # unused by current templates, kept in case you want it elsewhere
├── templates/
│   ├── home.html            # Marketing homepage
│   ├── thanks.html           # Post-inquiry thank-you page
│   ├── verify.html           # Public installer search page
│   ├── login.html            # Admin login page
│   └── admin_dashboard.html  # Admin-only: view/add/edit/delete installers
├── app.py
├── requirements.txt
├── setup.bat / setup.sh   # One-click first-time setup
├── run.bat / run.sh       # One-click run
└── database.db           # auto-created on first run (not in git)
```

## Admin access

- **Public visitors** (at `/verify`) can only search an Installer ID and see its status. They cannot view the full list or change anything.
- **Admin** (at `/admin/login`) can log in to add, edit, or delete installer records at `/admin`.

**Default login (for local testing only):**
```
Username: admin
Password: changeme123
```

**Before you go live, change these** by setting environment variables instead of using the defaults:

macOS / Linux:
```bash
export ADMIN_USERNAME="your_username"
export ADMIN_PASSWORD="your_strong_password"
export SECRET_KEY="a-long-random-string"
```

Windows (PowerShell):
```powershell
$env:ADMIN_USERNAME="your_username"
$env:ADMIN_PASSWORD="your_strong_password"
$env:SECRET_KEY="a-long-random-string"
```

`SECRET_KEY` signs the login session cookie — use a long random string (e.g. run `python -c "import secrets; print(secrets.token_hex(32))"` to generate one).

---

## Manual setup (if you prefer typing commands yourself)

1. **Open the folder** — `File > Open Folder...` and select `installer_portal`.

2. **Create a virtual environment** (Terminal > New Terminal):

   macOS / Linux:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   Windows:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **(Only if using the Python extension) Select the interpreter**: `Ctrl+Shift+P` / `Cmd+Shift+P` → "Python: Select Interpreter" → choose the one inside `.venv`. Skip this if you're not using the extension — the scripts and tasks above call `.venv`'s Python directly and don't need it.

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run it** — either:
   - Press **F5** (uses the "Python: Flask (app.py)" config in `.vscode/launch.json`, runs with the debugger attached), or
   - Open the integrated terminal and run:
     ```bash
     python app.py
     ```

6. Visit **http://127.0.0.1:5000** in your browser.

On first run, `app.py` auto-creates `database.db` and seeds it with the 39 real installer records from your training tracker.

## Notes

- `FLASK_DEBUG` and `PORT` can be overridden via environment variables (or edit `.vscode/launch.json`'s `env` block) if you want debug mode off or a different port.
- To reset the database (e.g. after editing seed data in `app.py`), just delete `database.db` and re-run — it will be rebuilt fresh.
- If VS Code's Python extension isn't installed yet, install the official **Python** extension from Microsoft — the "Python: Flask" debug config requires `debugpy`, which it installs automatically.
