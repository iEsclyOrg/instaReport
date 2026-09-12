<div align="center">

# ❓ Frequently Asked Questions

### InstaReport — FAQ

[← Back to README](README.md) &nbsp;·&nbsp; [Docs Index](docs/index.md)

</div>

---

## General

### What is InstaReport?

InstaReport is a premium social media automation platform developed and maintained by **iExly**. It combines an automated reporting engine, account management workflows, a cloud-hosted Telegram bot, profile lookup utilities and a secure online license system into one cross-platform product.

### Is InstaReport the same project as Credly / iEscly?

Yes. The project has evolved through multiple brands:

| Year | Brand |
|------|-------|
| 2021 | Credly |
| 2022 – 2026 | iEscly |
| 2026 – Present | iExly |

Your previous version knowledge still applies — the product simply operates under a new identity.

### Who maintains InstaReport?

InstaReport is officially maintained by the **iExly** organization. Any repository, seller or channel claiming to be official should be cross-checked against the [official resources](README.md#-beware-of-fake-copies).

---

## Compatibility

### Which operating systems are supported?

- Windows 10 / 11
- Ubuntu
- Kali Linux
- Debian
- Android (Termux)
- Cloud-hosted Telegram bot

### Do I need Python installed?

No. The Windows and Linux **standalone binaries** include everything required. No Python installation is needed.

### Does the Android (Termux) version require Python?

Yes — the Termux build runs as a Python package. It is distributed exclusively through **official channels**.

---

## Installation

### How do I install on Windows?

1. Download `InstaReport-Windows-x86-64.exe` from [GitHub Releases](https://github.com/iEsclyOrg/instaReport/releases).
2. Run the executable.
3. Enter your license key.

Full instructions are in the [Installation Guide](docs/installation.md).

### How do I install on Linux?

```bash
chmod +x InstaReport-Linux-x86_64.bin
./InstaReport-Linux-x86_64.bin
```

No Python installation required for the standalone binary.

---

## Licensing

### How do I purchase a license?

Visit the [official pricing page](https://iescly.duckdns.org/pricing) and choose the plan that fits your needs.

### How does license activation work?

1. Purchase a license.
2. Launch InstaReport.
3. Enter your activation key.
4. The app validates the key online against the licensing API and binds it to your device hardware ID.

### Can I use one license on multiple devices?

No. Licenses are bound to a device hardware ID and validated online.

### What if my license doesn't activate?

- Verify you are connected to the internet.
- Verify the key was entered exactly as provided (no extra spaces).
- Contact support via the [official Telegram channel](https://t.me/iescly).

### My license expired — what now?

Renew or purchase a new license via the [official pricing page](https://iescly.duckdns.org/pricing).

---

## Usage

### What can I report targets for?

The engine supports reports across multiple platforms, including **Instagram, YouTube, X (Twitter), Telegram, Discord, Reddit, TikTok, Facebook, Snapchat, Threads and Gmail**, with 8 selectable report reasons (Spam, Harassment, Impersonation, Hate speech, Nudity, Violence, Misinformation, Scam/Fraud).

### Can I schedule automatic reports?

Yes. The Telegram bot includes a **scheduler** (`/schedule`) that repeats the last report configuration at a set time each day, with optional repetition and interval settings.

### Can I bulk-import targets?

Yes. The desktop app's batch processor includes a **📂 Import .txt** button that loads targets from a file (one per line, `#` for comments).

### What is a "health pre-check"?

Before each campaign run, every account is tested for a valid login session. Dead or invalid accounts are **skipped automatically** to preserve campaign reliability.

---

## Telegram Bot

### Where is the official bot?

The official Telegram bot is [@instaReportV2Bot](https://t.me/instaReportV2Bot).

### Do I need a license to use the bot?

The bot requires an activated license for premium operations. Some commands may require activation.

### What commands are available?

See the full [Telegram Bot reference](docs/telegram.md).

### Is the bot available 24/7?

The bot is **cloud-hosted** and designed to operate 24/7.

---

## Discord Bot

### Is there a Discord bot?

Yes. The same engine, backend and license power a **Discord bot** available in the official server: <https://discord.com/invite/v6ebT5aFx>

### Do I need a separate license for Discord?

No. Your license works across both the Telegram and Discord bots.

### What commands does the Discord bot support?

See the [Discord Bot reference](docs/discord.md) for the full command list.

---

## Support & Refunds

### How do I get support?

Contact the official Telegram channel or review [SUPPORT.md](SUPPORT.md).

### Is there a refund policy?

Refund eligibility follows the terms published on the [official pricing page](https://iescly.duckdns.org/pricing). Contact support to request a refund.

---

## Security

### How do I report a vulnerability?

Please do **not** open a public issue for security problems. Follow the instructions in [SECURITY.md](SECURITY.md) to report privately.

### Is my data stored securely?

Local credential storage uses strong encryption (PBKDF2 with 480,000 iterations). Licenses are validated online and bound to your hardware ID.

---

<div align="center">

Copyright © 2021 – 2026 iExly. All rights reserved.

</div>
