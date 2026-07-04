# Azure App Service startup command (SPEC §7): set the app's
# "Startup Command" to  bash startup.sh
# Runs pending migrations, collects static files for WhiteNoise, then starts
# gunicorn — App Service's front end proxies port 8000.
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn --bind=0.0.0.0:8000 --workers=2 --timeout 120 config.wsgi
