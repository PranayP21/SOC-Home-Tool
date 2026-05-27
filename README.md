# SOC Home Tool - Raspberry Pi E-Ink Command Centre

A Raspberry Pi powered e-ink dashboard for home network monitoring, basic Mini SOC alerts, account-security email monitoring, weather, tasks, and calendar events.

Designed for a Raspberry Pi with a Waveshare-style 2.13 inch e-paper display.

## Features

- Rotating e-ink dashboard pages
- Mini SOC page
  - Internet status
  - Router status
  - DNS status
  - Unknown network device detection
  - Account security email monitoring
  - Risk level: LOW / MED / HIGH
- Home Status page
  - Internet/router/DNS
  - Wi-Fi signal
  - CPU/RAM/temp/uptime
- Personal Dashboard page
  - Weather via Open-Meteo
  - Tasks from `tasks.txt`
  - Calendar via private ICS/iCal URL
- Email alerts via SMTP
- Cached mailbox/calendar/weather checks to avoid slow refreshes
- systemd service for automatic startup

## Hardware

Recommended:

- Raspberry Pi 4, Raspberry Pi Zero 2 W, or similar
- Waveshare 2.13 inch e-Paper HAT/module
- MicroSD card
- Stable power supply

## Quick setup

Clone the repo on your Pi:

```bash
git clone https://github.com/PranayP21/SOC-Home-Tool.git
cd SOC-Home-Tool
```

Install dependencies:

```bash
chmod +x scripts/install_dependencies.sh
./scripts/install_dependencies.sh
```

Copy example configuration files:

```bash
cp config.example.yaml config.yaml
cp email_config.example.yaml email_config.yaml
cp account_monitor.example.yaml account_monitor.yaml
cp personal_dashboard.example.yaml personal_dashboard.yaml
cp tasks.example.txt tasks.txt
```

Create folders and cache files:

```bash
chmod +x scripts/setup_project.sh
./scripts/setup_project.sh
```

Edit your configuration files:

```bash
nano config.yaml
nano email_config.yaml
nano account_monitor.yaml
nano personal_dashboard.yaml
nano tasks.txt
```

Copy the Waveshare e-paper Python library into this project:

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/waveshare/e-Paper.git
cd SOC-Home-Tool
cp -r ~/projects/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd .
```

Test the display first:

```bash
cd ~/projects/e-Paper/RaspberryPi_JetsonNano/python/examples
sudo python3 epd_2in13_V4_test.py
```

Run the dashboard manually:

```bash
cd ~/projects/SOC-Home-Tool
sudo python3 app.py
```

Stop with `CTRL + C`.

## Automatic startup

Install the service:

```bash
cd ~/projects/SOC-Home-Tool
chmod +x scripts/install_service.sh
./scripts/install_service.sh
```

Check status:

```bash
sudo systemctl status eink-command-centre.service
```

View logs:

```bash
journalctl -u eink-command-centre.service -f
```

## Config files

### `config.yaml`

Main dashboard, router, DNS, device-scan, and page-rotation settings.

### `email_config.yaml`

SMTP settings used to send alerts from the Pi to your chosen recipient email. Use an app password, not your normal email password.

### `account_monitor.yaml`

IMAP mailbox settings used to read security-alert emails. For a safer setup, use a dedicated alert mailbox and forward security emails from other accounts to it.

### `personal_dashboard.yaml`

Weather and calendar settings. Calendar uses a private ICS/iCal URL.

## Security notes

Do not commit your real configuration files. The `.gitignore` file excludes private config files, cache files, logs, and copied Waveshare driver files.

Only commit the `*.example.yaml` files.

## Useful commands

Restart service:

```bash
sudo systemctl restart eink-command-centre.service
```

Stop service:

```bash
sudo systemctl stop eink-command-centre.service
```

View service status:

```bash
sudo systemctl status eink-command-centre.service
```

View app logs:

```bash
tail -f logs/app.log
```

Reset caches:

```bash
chmod +x scripts/reset_caches.sh
./scripts/reset_caches.sh
```

## Calendar setup

The Pi does not connect directly to the Samsung Calendar app. Sync Samsung Calendar to Google Calendar or Outlook Calendar, then use the private ICS/iCal URL in `personal_dashboard.yaml`.

See `docs/calendar_setup.md`.

## Remote SSH access

For remote access from another network, use Tailscale or another VPN. Avoid exposing SSH directly to the internet.

See `docs/remote_access_tailscale.md`.

## Disclaimer

This is a home-lab monitoring tool. It is not a replacement for a professional SOC, SIEM, EDR, IDS, or managed security service.
