#!/usr/bin/env bash
set -euo pipefail

mkdir -p data alerts logs

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

rm -f alerts/*.txt

echo "Caches and alert cooldowns reset."
