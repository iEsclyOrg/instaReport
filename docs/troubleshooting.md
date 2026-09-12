<div align="center">

# 🛠 Troubleshooting

### InstaReport — Common Issues & Solutions

[← Back to README](../README.md) &nbsp;·&nbsp; [Docs Index](index.md)

</div>

---

## License Issues

### License won't activate

- Ensure you are connected to the internet — activation is **online**.
- Verify the key is entered exactly as provided (no spaces or typos).
- Confirm the key is not already bound to another device.
- If activation is attempted too many times, the server may temporarily rate-limit you. Wait and retry.

### License expired

Renew or purchase a new license via the [official pricing page](https://iescly.duckdns.org/pricing).

### "Invalid license key"

- Double-check the key characters (`0` vs `O`, `1` vs `l`, etc.).
- Contact support via the official Telegram channel if the key was never used.

---

## Installation Issues

### Windows binary won't start

- Ensure Windows 10/11 is up to date.
- If SmartScreen warns, verify the download came from [official releases](https://github.com/iEsclyOrg/instaReport/releases) before allowing.
- Try running the executable from a fresh download.

### Linux binary permission denied

```bash
chmod +x InstaReport-Linux-x86_64.bin
./InstaReport-Linux-x86_64.bin
```

### Termux build errors

- Run `pkg update` first.
- Use the official Python build distributed via the official Telegram channel — do not install from third-party mirrors.
- Ensure you are using a supported Python version.

---

## Runtime Issues

### Reports are slow or failing

- Randomized delays (±30% jitter) are applied intentionally to avoid detection patterns — some slow-down is expected and healthy.
- Under rate limits, exponential backoff increases wait times automatically. Patience improves success rates.
- Verify accounts have valid login sessions — the health pre-check skips dead accounts.

### Too many attempts / rate limited

- The system applies backoff `min(10 × 2^attempt, 300s)`. Allow the retries to complete.
- Using proxies may help avoid rate limits. Misbehaving proxies are blacklisted automatically.

### Proxies not working

- Verify proxy details (host, port, credentials).
- Proxies that fail repeatedly are removed from rotation automatically — replace them and retry.

### OTP / 2FA not received

- OTP collection uses a **120-second timeout** window — respond promptly.
- Ensure the Telegram chat linked to the account is reachable.

---

## Telegram Bot Issues

### Bot not responding

- Confirm you messaged the **official** bot: <https://t.me/instaReportV2Bot>
- The bot is cloud-hosted; brief outages may occur.

### Commands don't work

- Some commands require an **activated license** — send `/activate CODE` first.
- Check `/status` to confirm your configuration.

---

## Update Issues

### Auto-update not triggering

- Update checks run at startup. Restart the app to trigger a check.
- You can always download the latest release from [GitHub Releases](https://github.com/iEsclyOrg/instaReport/releases).

---

## Still Stuck?

Contact the official support team via Telegram: <https://t.me/iescly>

Include your **platform**, **version** and a clear description of the problem to speed up resolution. See [SUPPORT.md](../SUPPORT.md) for details.

---

## Related

- [Installation Guide](installation.md)
- [FAQ](../FAQ.md)
- [Architecture](architecture.md)

---

<div align="center">

Copyright © 2021 – 2026 iExly. All rights reserved.

</div>
