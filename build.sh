#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Automatically load the database seed data if the database is empty
DB_SEEDED=$(python manage.py shell -c "
try:
    from shop.models import Category
    print('1' if Category.objects.exists() else '0')
except Exception:
    print('0')
")
if [[ "$DB_SEEDED" == *"1"* ]]; then
    echo "Database is already seeded. Skipping seed load."
else
    if [ -f "db_seed.json" ]; then
        echo "Database is empty. Loading database seed data..."
        python manage.py loaddata db_seed.json
    fi
fi

