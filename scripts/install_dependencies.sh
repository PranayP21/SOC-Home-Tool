#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y \
  git \
  arp-scan \
  net-tools \
  wireless-tools \
  fonts-dejavu-core \
  python3-yaml \
  python3-psutil \
  python3-pil \
  python3-requests \
  python3-spidev \
  python3-gpiozero \
  python3-lgpio

echo "Dependencies installed."
