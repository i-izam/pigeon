# PIGEON

A real-time 1-to-1 chat web app built with Django and Django Channels (WebSockets).

## Features

- Signup / login / logout with a custom Django User model (username + password)
- Users list and one-to-one chat pages
- Real-time messaging over WebSockets (Django Channels + Daphne)
- Chat history saved in the database
- WhatsApp-style chat bubbles, timestamps, auto-scroll, auto-reconnect

## Tech Stack

Python, Django, Django Channels, Daphne, SQLite, HTML/CSS/JavaScript

## Run locally

```
git clone https://github.com/<your-username>/pigeon.git
cd pigeon
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/ . To test chat, log in as two different users in two different browsers (or one normal + one incognito window).

## Notes

- Uses `InMemoryChannelLayer` for development. A production setup would use Redis.
- Planned: group chat, online status, unread counts.