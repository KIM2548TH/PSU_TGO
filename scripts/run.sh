#!/bin/bash
set -e

export PYTHONPATH=$(pwd)
export APP_SETTINGS=$(pwd)/.env  # <-- เพิ่มบรรทัดนี้

# รัน tailwind watch ผ่านสคริปต์ npm ของคุณ
./scripts/npm run tw:watch &

# รัน backend ผ่าน gunicorn
poetry run gunicorn "webapp.web:create_app()" --bind 0.0.0.0:5000 --workers 4

wait
