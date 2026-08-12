# HireHorizon

A small Flask job board — *Where Opportunities Meet Ambition*. An admin posts job openings
(company, role, image, details with an application link); registered users browse them and
leave comments.

**Stack:** Flask · SQLAlchemy 2.0 · Flask-Login · Flask-WTF · Flask-CKEditor ·
Bootstrap-Flask · Flask-Gravatar. Postgres in production, SQLite locally.

---

## Running on Termux (Android)

The app runs on your phone and is reachable from any device on the same Wi-Fi.

### 1. Install the system packages

```bash
pkg update && pkg upgrade
pkg install python clang binutils git
pkg install termux-api        # optional: wake-lock and Wi-Fi IP lookup
```

`clang` is not optional — SQLAlchemy pulls in `greenlet` on ARM64, and it has no Android
wheel, so pip has to compile it.

### 2. Clone and start

```bash
git clone <repo-url>
cd HireHorizon
bash run.sh
```

`run.sh` creates a virtualenv, installs `requirements-termux.txt`, takes a wake-lock, and
serves the app with gunicorn on port 8000. The first run takes a few minutes while greenlet
compiles.

### 3. Open it

On the phone itself: <http://localhost:8000>

From a laptop or another phone on the same Wi-Fi, you need the phone's LAN IP. `ip addr` is
usually blocked for unprivileged apps on Android 10+, so use either:

```bash
termux-wifi-connectioninfo   # read the "ip" field (needs termux-api)
```

...or just check **Settings → Wi-Fi → your network → IP address**. Then browse to
`http://<that-ip>:8000`.

If the phone answers on `localhost` but nothing else on the network can reach it, the cause
is almost always **client isolation / AP isolation** on your router, not the app.

### 4. Admin account

`admin_only` in `main.py` hardcodes **user id 1** — whoever registers first owns the site.

The repo ships a populated `instance/posts.db` whose id 1 is `admin@gmail.com`. If you don't
know that password, delete the file before the first run:

```bash
rm instance/posts.db
```

The schema is recreated on startup, and the first account you register becomes the admin.

### 5. Keeping it running

- **Wake-lock** — `run.sh` calls `termux-wake-lock` automatically when termux-api is installed.
- **Battery optimization** — exempt Termux in Android settings, or the OS will kill it.
- **Start on boot** — install the [Termux:Boot](https://wiki.termux.com/wiki/Termux:Boot)
  addon and put a script in `~/.termux/boot/` that runs `bash ~/HireHorizon/run.sh`.
- **Stable address** — the IP changes between networks. A DHCP reservation on your router
  pins it so you don't have to look it up again.

### Troubleshooting

**pip fails building SQLAlchemy.** Termux ships Python 3.13, which the pinned
`SQLAlchemy==2.0.25` predates. Relax that one line in `requirements-termux.txt` to
`SQLAlchemy>=2.0.31`. If it still fails, install an older interpreter:
`pkg install tur-repo && pkg install python3.11`, then recreate the venv with it.

**gunicorn misbehaves.** Fall back to the Flask dev server, which binds the same way:

```bash
. .venv/bin/activate && python main.py
```

**Every job you post shows up as a git diff.** `instance/posts.db` is a tracked file. To stop
that: `git rm --cached instance/posts.db` and add `instance/` to `.gitignore`. Note that
afterwards a fresh clone starts with an empty database.

---

## Configuration

Everything is optional — the app boots with no `.env` at all.

| Variable | Default | Purpose |
|---|---|---|
| `secret_key` | random per restart | Flask session/CSRF key. Set it so logins survive a restart. |
| `DB_URI` | `sqlite:///posts.db` | Database URL. Set to a Postgres URL in production. |
| `HOST` | `0.0.0.0` | Bind address for `python main.py`. Use `127.0.0.1` for phone-only access. |
| `PORT` | `8000` | Port to listen on. Termux is unprivileged, so keep it above 1024. |
| `own_email` / `own_password` | unset | Gmail address and app password for the contact form. Unset means submissions are silently skipped rather than erroring. |

Put them in a `.env` file in the project root; it is gitignored.

## Production deploy

`requirements.txt` (with `psycopg2-binary`) and the `Procfile` target a Render/Heroku-style
host running `gunicorn main:app`. Set `DB_URI` and `secret_key` there.

## Access control

Admin is **user id 1** — whoever registers first. `admin_only` guards `/new-post`,
`/edit-post/<id>` and `/delete/<id>`: anonymous visitors are redirected to the login page,
signed-in non-admins get a 403.

`/delete/<id>` is POST-only and rendered as a form, so it can't be triggered by a link
prefetcher. CSRF protection is app-wide (`CSRFProtect`), which means any hand-written
`<form method="post">` you add needs a token:

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
```

Forms rendered through bootstrap-flask's `render_form` already include one.

## Known issues

- Commenting on a post doesn't redirect after the insert, so refreshing the page posts the
  comment again.
- Anyone who registers can comment; there is no moderation or rate limiting.
