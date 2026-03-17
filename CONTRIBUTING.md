# Contributing to Bluesky Crosspost Bot

Thank you for your interest in contributing! Here is everything you need to get started.

---

## Reporting Issues

Before opening a new issue, please:

1. Check the [existing issues](https://github.com/kitradrago/bluesky-crosspost/issues) to avoid duplicates.
2. Include the following in your report:
   - Steps to reproduce the problem
   - What you expected to happen
   - What actually happened
   - Relevant log output (from the **Logs** tab in the web UI, or `docker-compose logs`)
   - Your deployment type (generic Docker, Unraid, etc.)

---

## Suggesting Features

Open an issue with the title prefixed by `[Feature Request]`. Describe the use case and how the feature would work.

---

## Submitting Pull Requests

1. **Fork** the repository and create a branch from `main`:

   ```bash
   git checkout -b feature/my-improvement
   ```

2. **Make your changes.** Keep commits focused — one logical change per commit.

3. **Test locally** before submitting:

   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   # fill in test credentials
   python src/main.py
   ```

4. **Open a pull request** against the `main` branch. Describe what you changed and why.

---

## Development Setup

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for container testing)

### Local run

```bash
git clone https://github.com/kitradrago/bluesky-crosspost.git
cd bluesky-crosspost
pip install -r requirements.txt
cp .env.example .env
# Edit .env with credentials
python src/main.py
```

### Docker build

```bash
docker-compose build
docker-compose up
```

---

## Code Style

- Follow existing file and function naming conventions.
- Keep functions focused and small.
- Add a brief comment for any non-obvious logic.
- Do not commit `.env` or any file containing real credentials.

---

## Project Layout

```
bluesky-crosspost/
├── src/
│   ├── main.py             # Application entry point
│   ├── config.py           # Environment variable loading
│   ├── webui.py            # Web management UI (aiohttp)
│   ├── bluesky_client.py   # Bluesky API integration
│   ├── telegram_client.py  # Telegram Bot API integration
│   └── discord_client.py   # Discord bot integration
├── .env.example            # Environment variable template
├── docker-compose.yml
├── Dockerfile
└── unraid-docker-template.xml
```

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
