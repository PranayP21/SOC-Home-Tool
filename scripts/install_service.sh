#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_USER="${SUDO_USER:-$(whoami)}"

sudo tee /etc/systemd/system/eink-command-centre.service > /dev/null << EOF
[Unit]
Description=Pi E-Ink Command Centre
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=${PROJECT_DIR}
ExecStart=/usr/bin/python3 ${PROJECT_DIR}/app.py
Restart=always
RestartSec=10
User=${PROJECT_USER}
Group=${PROJECT_USER}

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/sudoers.d/eink-command-centre > /dev/null << EOF
${PROJECT_USER} ALL=(root) NOPASSWD: /usr/bin/arp-scan
EOF

sudo chmod 440 /etc/sudoers.d/eink-command-centre
sudo systemctl daemon-reload
sudo systemctl enable eink-command-centre.service
sudo systemctl restart eink-command-centre.service

echo "Service installed and started."
echo "Check status with: sudo systemctl status eink-command-centre.service"
