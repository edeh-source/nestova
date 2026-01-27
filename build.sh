#!/usr/bin/env bash
# exit on error
set -o errexit

echo "🚀 Starting Nestova deployment build process..."

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --no-input

# Run database migrations
echo "🗄️  Running database migrations..."
python manage.py migrate

# ============================================
# POPULATE DATABASE WITH INITIAL DATA
# ============================================

echo "🌍 Populating database with initial data..."

# 1. Populate Nigerian States and Cities
echo "  → Populating locations (states and cities)..."
python manage.py populate_locations

# 2. Populate Property Types
echo "  → Populating property types..."
python manage.py populate_type

# 3. Populate Nigerian Banks
echo "  → Populating Nigerian banks..."
python manage.py populate_bank

# 4. Create Sample Properties (optional - comment out if not needed)
echo "  → Creating dummy properties..."
python manage.py create_dummy_properties || echo "⚠️  Warning: Failed to create dummy properties (may already exist)"

# 5. Populate Blog Categories and Posts
echo "  → Populating blog posts..."
python manage.py populate_blogs || echo "⚠️  Warning: Failed to populate blogs (may already exist)"

# 6. Publish Draft Posts
echo "  → Publishing draft blog posts..."
python manage.py publish_posts || echo "⚠️  Warning: No draft posts to publish"

# 7. Create Sample Apartments (optional - comment out if not needed)
echo "  → Creating sample apartments..."
python manage.py create_sample_apartment --count 10 || echo "⚠️  Warning: Failed to create sample apartments (may already exist)"

# 8. Populate Bookings (optional - comment out if not needed)
echo "  → Populating booking apartments..."
python manage.py populate_bookings || echo "⚠️  Warning: Failed to populate bookings (may already exist)"

python manage.py createsuperuser

echo "✅ Build process completed successfully!"
echo "🎉 Nestova is ready for deployment!"
