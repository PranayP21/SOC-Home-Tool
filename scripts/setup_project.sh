#!/usr/bin/env bash
set -euo pipefail

mkdir -p data alerts logs

touch data/known_devices.txt
touch data/seen_account_alerts.txt

cat > data/account_alert_cache.yaml << 'EOF'
last_scan_time: 0
last_alert_count: 0
last_alerts: []
EOF

cat > data/weather_cache.yaml << 'EOF'
last_scan_time: 0
weather: {}
EOF

cat > data/calendar_cache.yaml << 'EOF'
last_scan_time: 0
events: []
EOF

chmod 600 email_config.yaml account_monitor.yaml personal_dashboard.yaml 2>/dev/null || true

echo "Project folders and cache files created."
