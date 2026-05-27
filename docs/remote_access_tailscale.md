# Remote SSH Access with Tailscale

**Do not expose SSH directly to the internet unless you understand the risks.**

The recommended approach is Tailscale.

## Install Tailscale on the Pi

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Open the login URL and sign in.

Get the Pi's Tailscale IP:

```bash
tailscale ip -4
```

Example output:

```text
100.80.45.12
```

## Install Tailscale on your laptop/PC

Install Tailscale, sign in with the same account, then SSH to the Pi:

```bash
ssh pi-user@100.80.45.12
```

Replace `pi-user` with your Raspberry Pi username and the IP with your Pi's Tailscale IP.

## Useful remote maintenance commands

```bash
sudo systemctl status eink-command-centre.service
sudo systemctl restart eink-command-centre.service
journalctl -u eink-command-centre.service -f
nano ~/SOC-Home-Tool/config.yaml
```
