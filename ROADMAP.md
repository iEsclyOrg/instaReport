# 🗺 Roadmap

**InstaReport** is under active development. This roadmap reflects the current direction and planned work. Items may shift based on user feedback and priorities.

---

## Recently Shipped — v8.7.5

- ✅ Randomized action delays (±30% jitter) to mimic human behavior
- ✅ Exponential backoff on retry (`min(10 × 2^attempt, 300s)`)
- ✅ Account health pre-check before campaigns
- ✅ Bulk target import from `.txt`
- ✅ Auto-update check on startup
- ✅ Campaign resume infrastructure (SQLite-backed progress)
- ✅ Stealth & safe modes, proxy support with blacklisting

---

## In Progress

- 🔄 **Campaign Resume button** — enable resuming interrupted campaigns directly from the UI (infrastructure is already in place).
- 🔄 **Expanded platform coverage** — additional report targets and automation workflows.
- 🔄 **Telegram bot enhancements** — deeper account management and automation controls.

---

## Planned

- 🚧 More granular scheduling options (custom recurrence rules).
- 🚧 Additional report reason localizations.
- 🚧 Extended profile lookup utilities.
- 🚧 Performance optimizations and faster batch processing.
- 🚧 Better onboarding for new licensees.

---

## Under Consideration

- 💡 A community showcase/feedback channel.
- 💡 More self-service documentation and video guides.
- 💡 Wider device support (including future platforms).

---

## How to Influence the Roadmap

User feedback drives prioritization. Share requests through:

- The official Telegram channel: <https://t.me/iescly>
- The [official website](https://iescly.duckdns.org)

Feature requests are collected and reviewed against community impact, effort and strategic fit.

---

## Related

- [CHANGELOG.md](CHANGELOG.md)
- [SUPPORT.md](SUPPORT.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
