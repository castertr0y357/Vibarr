#!/bin/sh

# Exit immediately if a command exits with a non-zero status
set -e

# Drop privileges to vibarr user if running as root
if [ "$(id -u)" = '0' ]; then
    echo "Fixing permissions on logs, data, and staticfiles directories..."
    chown -R vibarr:vibarr /app/logs /app/data /app/staticfiles
    echo "Dropping privileges to vibarr user..."
    exec gosu vibarr "$0" "$@"
fi


if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Start the application or worker
# We use the first argument passed to the script
SERVICE_TYPE=${1:-web}

if [ "$SERVICE_TYPE" = "worker" ]
then
    echo "Starting Django-Q worker..."
    exec python manage.py qcluster
else
    # Apply database migrations
    echo "Applying database migrations..."
    python manage.py migrate --no-input

    # Initialize background task schedules
    echo "Initializing background task schedules..."
    python manage.py initialize_schedules

    # Collect static files
    echo "Collecting static files..."
    python manage.py collectstatic --no-input

    # Create superuser if environment variables are set
    if [ "$DJANGO_SUPERUSER_USERNAME" ]
    then
        echo "Ensuring superuser exists..."
        # Using a management command to create superuser if it doesn't exist
        python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists() or User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')"
    fi

    echo "Starting Gunicorn server on internal port 8000..."
    exec gunicorn vibarr_project.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 3 \
        --access-logfile - \
        --error-logfile -
fi
