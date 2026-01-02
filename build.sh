#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Prepopulate database with verified management commands
echo "Populating locations..."
python manage.py populate_locations
echo "Populating property types..."
python manage.py populate_type
echo "Creating dummy properties..."
python manage.py create_dummy_properties
echo "Populating blog data..."
python manage.py populate_blogs
echo "Populating bookings..."
python manage.py populate_bookings
echo "Publishing posts..."
python manage.py publish_posts

echo "Database prepopulation complete."
