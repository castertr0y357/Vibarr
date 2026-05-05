#!/bin/sh

if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate

# Create superuser if environment variables are set
if [ "$DJANGO_SUPERUSER_USERNAME" ]
then
    echo "Creating superuser..."
    python manage.py createsuperuser \
        --no-input \
        --username $DJANGO_SUPERUSER_USERNAME \
        --email $DJANGO_SUPERUSER_EMAIL
fi

# Start the application or worker
if [ "$SERVICE_TYPE" = "worker" ]
then
    echo "Starting Django-Q worker..."
    python manage.py qcluster
else
    echo "Starting Gunicorn server..."
    exec gunicorn vibarr_project.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3
fi
