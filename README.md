# HireHorizon

**Where Ideas Find Their Horizon.**

A text-first social blogging platform built with Django — the rhythm of a social
feed (follow, like, reply, repost, message) with room to write something longer
than a status update.

**HireHorizon accepts no image uploads anywhere.** Not on posts, not on comments,
not on profiles. Avatars are rendered from initials in CSS. That is a product
decision, and it also removes an entire class of security and moderation problems.

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # optional for local dev
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000>. The admin is at `/admin/`.

## Features

| Area | What you get |
|---|---|
| Posts | Title + long-form body, slugs, draft/published, edit, delete |
| Feed | Posts from people you follow, plus your own, paginated |
| Social | Follow/unfollow, like, comment (with replies), repost, bookmark |
| Mentions | `@username` links to the profile and notifies that user |
| Messaging | Private text conversations, participants only |
| Notifications | Follows, likes, comments, replies, mentions, reposts, messages |
| Search | People and posts, in separate tabs |
| Explore | Trending (7-day engagement), Latest, People to follow |
| Contact | Saves to the database and appears in the admin — no email involved |

## Project layout

```
config/           settings, root URLs, WSGI
apps/accounts/    custom User, Follow, auth + profile views
apps/blog/        Post, Comment, Like, Bookmark, Repost, PostView
apps/messaging/   Conversation, ConversationParticipant, Message
apps/notifications/  Notification (generic relation to any target)
apps/core/        landing/feed/explore/search/contact, error handlers, utils
templates/        server-rendered templates, mobile-first
static/           one stylesheet, one small JS file, no build step
```

## URLs

```
/                      landing (anonymous) or your feed (signed in)
/explore/  /search/  /about/  /contact/
/login/  /register/  /logout/
/settings/  /settings/profile/  /settings/password/
/post/create/  /post/<slug>/  /post/<slug>/edit/  /post/<slug>/delete/
/@<username>/  /@<username>/followers/  /@<username>/following/
/notifications/  /messages/  /messages/<id>/  /bookmarks/
```

## Configuration

Everything is environment-driven; see `.env.example`. Nothing is hardcoded and
there are no SMTP settings, because the app sends no email.

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | generated in DEBUG | **Required** when `DEBUG=False` — the app refuses to start without it |
| `DEBUG` | `True` | Set `False` for anything reachable by other people |
| `ALLOWED_HOSTS` | `*` in DEBUG | Comma-separated. Required when `DEBUG=False` |
| `CSRF_TRUSTED_ORIGINS` | empty | Needed behind HTTPS or a tunnel; include the scheme |
| `DATABASE_URL` | SQLite | e.g. `postgres://user:pass@host:5432/db` |
| `HTTPS_ENABLED` | `False` | Only `True` when actually served over TLS |
| `PAGE_SIZE` | `20` | Items per page |

Generate a key with `python manage.py generate_secret_key`.

## Superuser and admin

```bash
python manage.py createsuperuser
```

Every model is registered with list displays, filters and search: Users, Follows,
Posts, Comments, Likes, Bookmarks, Reposts, PostViews, Conversations, Messages,
Notifications and Contact Messages.

There is **no email-based password reset**, because there is no mail backend. To
reset a password: `python manage.py changepassword <username>`.

## Migrating from the old Flask version

The pre-Django app stored data in `instance/posts.db`. To bring it across:

```bash
python manage.py import_legacy --dry-run    # see what would happen
python manage.py import_legacy
```

Posts and comments transfer intact; the old `subtitle` is folded into the body
and the `img_url` column is dropped, since the app is text-only now. **Passwords
cannot transfer** — the Flask app used Werkzeug's hash format, which Django's
hashers do not understand — so imported accounts get an unusable password and
need `changepassword`.

---

## Running on Termux (Android)

### 1. Install the system packages

```bash
pkg update && pkg upgrade
pkg install python git
pkg install termux-api        # optional: wake-lock and Wi-Fi IP detection
```

No compiler is needed: nothing in `requirements-termux.txt` has a C extension.

### 2. Clone and start

```bash
git clone <repo-url>
cd HireHorizon
bash run.sh
```

`run.sh` creates the virtualenv, installs dependencies, runs migrations, detects
the phone's Wi-Fi address and prints the exact URL to open:

```
  On this phone:     http://localhost:8000
  On other devices:  http://192.168.1.37:8000
```

Create your admin account with `python manage.py createsuperuser` once the
virtualenv exists (`source .venv/bin/activate` first).

### 3. Keeping it running

- **Battery optimization** — exempt Termux in Android settings, or the OS kills it.
- **Wake-lock** — `run.sh` calls `termux-wake-lock` when termux-api is installed.
- **On boot** — install Termux:Boot and put `bash ~/HireHorizon/run.sh` in `~/.termux/boot/`.
- **Stable address** — a DHCP reservation on your router keeps the IP from moving.

### Other devices can't reach it

Work down this list; the first two cover almost every case.

1. **Wrong address.** Use the one `run.sh` prints, and include the `http://`
   prefix — some browsers treat `192.168.1.37:8000` as a search term.
2. **Different subnet.** Compare the first three numbers of both devices' IPs
   (`192.168.1.x` vs `192.168.0.x`). A guest network, or 2.4GHz and 5GHz exposed
   as separate SSIDs, puts them on networks that cannot reach each other. Join
   both devices to the same SSID.
3. **AP / client isolation.** Same subnet but the connection times out: many
   routers block client-to-client traffic, especially on guest networks. Turn off
   "AP isolation" / "client isolation" in the router admin page.
4. **`DisallowedHost` error.** Add the phone's IP to `ALLOWED_HOSTS` in `.env`.
   `run.sh` does this automatically when it can detect the IP.

The failure mode tells you which: **timed out** means nothing answered (isolation
or wrong subnet); **connection refused** means something answered and declined
(wrong port, or that IP is a different device).

---

## 127.0.0.1 vs 0.0.0.0 vs the public Internet

These are three different things, and only the first two are about binding.

- **`127.0.0.1:8000`** — the loopback interface. Reachable *only from the phone
  itself*. Nothing else on your Wi-Fi can connect, by design.
- **`0.0.0.0:8000`** — every network interface on the device. Now any device
  **on the same local network** can reach it at the phone's LAN IP. This is what
  `run.sh` uses.
- **The public Internet** — binding to `0.0.0.0` does **not** provide this.

Your phone sits behind your router's NAT and behind your mobile carrier's
network. Machines on the Internet have no route to it. Binding to `0.0.0.0`
changes nothing about that; it only widens which *local* interfaces are served.

To let someone outside your Wi-Fi reach the app you need one of:

| Option | How it works | Trade-off |
|---|---|---|
| **Tunnel** (Cloudflare Tunnel, ngrok, tailscale funnel) | An outbound connection from the phone to a relay; the relay gives you a public HTTPS URL | Easiest and safest — no inbound ports opened. URL may rotate on the free tiers |
| **Port forwarding** | Router forwards an external port to the phone | Exposes the phone directly. Needs a static/dynamic-DNS address, and many ISPs use CGNAT which makes it impossible |
| **VPS / hosting** | Run Django on a rented server instead | Costs money, but is the right answer for anything real |
| **Tailscale / WireGuard** | Private network between your own devices | Only people you invite can reach it — ideal for personal use |

### Before you expose it to anyone

Exposing a phone to the Internet is a real security decision, not a checkbox:

- Set `DEBUG=False` and a real `SECRET_KEY`. With `DEBUG=True`, Django serves a
  full traceback with settings and local variables to anyone who triggers an error.
- Set `ALLOWED_HOSTS` to the exact hostname, not `*`.
- Set `CSRF_TRUSTED_ORIGINS` to the public origin, including `https://`.
- Set `HTTPS_ENABLED=True` **only** once traffic really is HTTPS end to end
  (tunnels give you this; plain port forwarding does not). Over plain HTTP it
  forces a redirect loop and the site becomes unreachable.
- Your phone becomes a server: it is reachable by scanners within minutes of
  going public, it has no firewall in front of it, and everything in the database
  — including private messages — is only as protected as this app's code.
- `runserver` is a development server. For real exposure use gunicorn:
  `gunicorn config.wsgi:application --bind 0.0.0.0:8000`.

Prefer a tunnel over port forwarding, and prefer a VPS over both if the site
matters.

---

## Production notes

With `DEBUG=False`:

- WhiteNoise serves the compressed, hashed static files — run `collectstatic` first.
- `SECRET_KEY` and `ALLOWED_HOSTS` are mandatory.
- `python manage.py check --deploy` is clean once `HTTPS_ENABLED=True`.

```bash
DEBUG=False SECRET_KEY=... ALLOWED_HOSTS=example.com python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

## Tests

```bash
python manage.py test
```

68 tests cover authentication, post ownership, the view-count rule, likes,
follows (including database-level duplicate and self-follow prevention),
comments, message privacy, bookmarks, contact submissions, notifications and
template escaping.

## Security posture

- CSRF protection on every mutating route; state changes are POST-only.
- Object-level ownership checks in the view layer, so hiding a button in a
  template is never the only protection.
- Private messages are readable only by conversation participants.
- All user text is escaped by Django's template autoescaping; the `@mention`
  linkifier escapes **before** inserting links.
- Database constraints enforce the rules that matter: one like per user per post,
  one view per user per post, no duplicate or self-follows.
- No file uploads at all, so there is no upload attack surface.
- Login errors do not reveal whether a username exists.
