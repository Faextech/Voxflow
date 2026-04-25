release: flask db upgrade
web: gunicorn "run:create_app()" -c gunicorn.conf.py
