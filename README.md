# Bluesky Crosspost Bot

Automatically cross-post Bluesky posts to Telegram, Discord and FurAffinity with a built-in web UI for configuration and monitoring.

## Features

- 🚀 Monitors a Bluesky account and cross-posts new content to Telegram, Discord and/or FurAffinity
- 🌐 Web-based management UI (port 2759) — no command line needed after setup
- 🔐 Encrypted credential storage; admin password protected with Fernet encryption
- 📊 Activity dashboard showing post history and delivery stats
- 📋 Real-time log viewer in the browser
- 🔄 One-click restart that reloads updated settings
- ⏭️ Skips replies — only original posts are cross-posted
- 🐳 Works with generic Docker Compose and Unraid

## Why I made this

We use a cloud service for posting to bluesky and a couple other locations, but none of them seem to cover crossposting to telegram, discord, and furaffinity. Some will do one or the other, or a couple of them, but none do all of them. So I decided to make my own application to run locally that would cross post things to other less common services. I can add others later as needed (either upon request, merges, or because I need it. I also made sure that everything could be configured through the webui, and that there were functions to potentially re-crosspost an item if there was a failure.

## How do I support you

If you would like to support me, please consider sending a donation to my GoFundMe for my medical needs. Its location here - https://www.gofundme.com/f/help-kitra-live-authentically

## Future possible enhancements:
- Toggle whether you want self-replies crossposted as well, and to what services.
- Graphical representation of community engagement.
- Potentially incorporating a notification function for if community replies with a question or specific hashtags (i.e. #question)

---

## Requirements

- Docker & Docker Compose
- Bluesky account with an app password (not your main password)
- Telegram bot token and channel ID (optional)
- Discord bot token and channel ID (optional)
- FurAffinity account (optional)

## Installation

### Docker (Generic)
## Quick Start (5 minutes)

git clone https://github.com/kitradrago/bluesky-crosspost.git
cd bluesky-crosspost
cp .env.example .env
# (Optional) edit .env with your credentials now, or configure via the web UI later
docker-compose up -d

Open https://<your-server-ip>:2759 in your browser.
Default login: admin / admin (change this immediately in the web UI under Admin Settings).

Note: The browser will warn about a self-signed certificate — this is expected. Accept the certificate to continue.

---

## Setup Instructions

### Generic Docker (docker-compose)

1. Clone the repository

   git clone https://github.com/kitradrago/bluesky-crosspost.git
   cd bluesky-crosspost

2. Create your .env file

   cp .env.example .env

   Fill in at minimum:
   BLUESKY_HANDLE=yourhandle.bsky.social
   BLUESKY_PASSWORD=your-app-password
   BLUESKY_TARGET_HANDLE=yourhandle.bsky.social

   Set CONFIG_DIR if you want data stored outside the project directory:
   CONFIG_DIR=/opt/bluesky-crosspost/config

3. Start the container

   docker-compose up -d

4. Access the web UI at https://localhost:2759

All persistent data (config, logs, post history) is stored under ./config/ (or your CONFIG_DIR).

---

### Unraid (via Community Applications or Compose)

#### Option A — Compose Stack (recommended)

1. In Unraid, go to Docker → Compose and create a new stack named bluesky-crosspost.
2. Paste the contents of docker-compose.yml into the editor.
3. Set variables in the stack's compose variables or a .env file at the stack path.
4. Set CONFIG_DIR to your appdata path, for example:
   CONFIG_DIR=/mnt/user/appdata/bluesky-crosspost
5. Click Deploy.

#### Option B — Unraid Template

Import unraid-docker-template.xml from this repository into your Unraid template library and fill in the required fields.

#### Key variables for Unraid

CONFIG_DIR | /mnt/user/appdata/bluesky-crosspost
WEBUI_PORT | 2759
LOG_LEVEL | INFO

After the container starts, open https://<unraid-ip>:2759 to finish setup through the web UI.

---

### Configuration via Web UI

The web UI is the easiest way to configure the bot after the container is running:

1. Open https://<server-ip>:2759 and log in (default: admin / admin).
2. Navigate to the Setup tab.
3. Enter your Bluesky credentials, Telegram token/channel, Discord token/channel, and/or FurAffinity username.
4. Click Save Settings.
5. Click Restart Now in the banner that appears — this applies the new settings.

Settings are saved to /config/.env inside the container (persistent volume) and take effect after restart.

### Configuration via .env file

You can also configure everything before starting the container. Copy .env.example to .env and fill in your values:

# Required
BLUESKY_HANDLE=yourhandle.bsky.social
BLUESKY_PASSWORD=your-app-password-here
BLUESKY_TARGET_HANDLE=yourhandle.bsky.social

# Optional — Telegram
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHANNEL_ID=-1001234567890

# Optional — Discord
DISCORD_ENABLED=true
DISCORD_BOT_TOKEN=MTA4NzQ1...
DISCORD_CHANNEL_ID=1087459487405...

# Optional — FurAffinity
FURAFFINITY_ENABLED=true
FURAFFINITY_USERNAME=your_fa_username

# Admin UI
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin

---

## Getting API Keys

### Bluesky App Password

Use an app password, not your login password. App passwords have limited scope and can be revoked independently.

1. Log in at bsky.app.
2. Go to Settings → Privacy and security → App Passwords.
3. Click Add App Password, give it a name (e.g., crosspost-bot).
4. Copy the generated password — it will only be shown once.

Use this as your BLUESKY_PASSWORD. Your BLUESKY_HANDLE is your handle like yourname.bsky.social.

---

### Telegram Bot Token

1. Open Telegram and search for @BotFather.
2. Send /newbot and follow the prompts to choose a name and username.
3. BotFather will send you a token like 123456789:AAF... — this is your TELEGRAM_BOT_TOKEN.
4. Add the bot to your channel as an administrator with "Post Messages" permission.
5. Get your channel ID:
   - Forward any message from your channel to @userinfobot.
   - The channel ID is shown (negative number for private channels, e.g., -1001234567890).

Set TELEGRAM_ENABLED=true and fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID.

---

### Discord Bot Token

1. Go to the Discord Developer Portal.
2. Click New Application, give it a name.
3. Go to the Bot section and click Reset Token to generate a token.
4. Copy the token — this is your DISCORD_BOT_TOKEN.
5. Under Privileged Gateway Intents, enable Message Content Intent.
6. Go to OAuth2 → URL Generator:
   - Scopes: bot
   - Bot Permissions: Send Messages, Embed Links
7. Open the generated URL to invite the bot to your server.
8. Get the channel ID: Enable Developer Mode in Discord (Settings → Advanced), then right-click the target channel and choose Copy Channel ID.

Set DISCORD_ENABLED=true and fill in DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID.

---

### FurAffinity Setup

Note: FurAffinity does not have an official API. The integration uses web scraping to post content. Ensure your account credentials are secure.

1. You will need a FurAffinity account with posting privileges.
2. For FurAffinity, you only need your username:
   - Set FURAFFINITY_ENABLED=true
   - Set FURAFFINITY_USERNAME=your_fa_username
3. The bot will use your configured Bluesky post content to create posts on FurAffinity.

Important: Keep your FurAffinity credentials confidential. The bot stores them encrypted.

---

## Configuration Reference

BLUESKY_HANDLE | Your Bluesky login handle | (required)
BLUESKY_PASSWORD | Bluesky app password (not your login password) | (required)
BLUESKY_TARGET_HANDLE | Account to monitor for new posts | (required)
BLUESKY_CHECK_INTERVAL | How often to poll for new posts, in seconds | 300
TELEGRAM_ENABLED | Enable Telegram posting (true/false) | false
TELEGRAM_BOT_TOKEN | Telegram bot token from @BotFather | (required if enabled)
TELEGRAM_CHANNEL_ID | Target Telegram channel ID | (required if enabled)
DISCORD_ENABLED | Enable Discord posting (true/false) | false
DISCORD_BOT_TOKEN | Discord bot token from the Developer Portal | (required if enabled)
DISCORD_CHANNEL_ID | Target Discord channel ID | (required if enabled)
FURAFFINITY_ENABLED | Enable FurAffinity posting (true/false) | false
FURAFFINITY_USERNAME | FurAffinity username for posting | (required if enabled)
ADMIN_USERNAME | Web UI login username | admin
ADMIN_PASSWORD | Web UI login password (encrypted at rest) | admin
LOG_LEVEL | Logging verbosity: DEBUG, INFO, WARNING, ERROR | INFO
CONFIG_DIR | Host path mapped to /config in the container | ./config
WEBUI_PORT | Port for the web management UI | 2759

All settings can be changed via the web UI without editing files.

---

## Troubleshooting

### Container starts but Bluesky isn't posting

- Open the web UI and check the Logs tab for error messages.
- Confirm your handle and app password are correct in the Setup tab.
- Make sure you're using an app password, not your Bluesky login password.
- After saving settings, click Restart Now — settings require a restart to take effect.

### Settings saved in the web UI don't apply after restart

- Ensure the /config volume is persistent (check your CONFIG_DIR or compose volume mapping).
- Settings are written to /config/.env. Verify the file exists and contains your values:
  docker exec bluesky-crosspost cat /config/.env
- Use the Restart Now button in the web UI (not a manual container stop/start), which ensures a clean reload.

### Telegram messages not sending

- Verify the bot was added to the channel as an administrator.
- For private channels the TELEGRAM_CHANNEL_ID must be negative (e.g., -1001234567890).
- Set TELEGRAM_ENABLED=true in settings.

### Discord messages not sending

- Verify the bot is in the server and has Send Messages and Embed Links permissions in the target channel.
- Confirm DISCORD_CHANNEL_ID is the numeric ID of the channel (not the channel name).
- Set DISCORD_ENABLED=true in settings.

### FurAffinity posts not sending

- Verify your FurAffinity username is correct in settings.
- Check the Logs tab for authentication errors.
- Ensure your FurAffinity account has posting privileges.
- Set FURAFFINITY_ENABLED=true in settings.
- FurAffinity uses web scraping; if the site structure changes, posts may fail until the bot is updated.

### Browser shows certificate warning

The web UI uses a self-signed TLS certificate generated on first start. Accept the warning in your browser to proceed.
The certificate is stored at /config/data/certs/ and persists across restarts.

### Can't log in to the web UI

- Default credentials are admin / admin.
- If you changed the password and can't remember it, edit /config/.env directly and set ADMIN_PASSWORD=admin, then restart.

---

## Monitoring

### View Logs

# Follow live container output
docker-compose logs -f bluesky-crosspost

# Or check the log file directly
docker exec bluesky-crosspost tail -f /config/logs/crosspost.log

The Logs tab in the web UI shows the last 50–500 lines of the application log.

### Activity Dashboard

The Activity tab shows:
- Total posts cross-posted
- Success/failure breakdown
- Per-platform delivery counts (Telegram, Discord, FurAffinity)
- A timestamped history table of recent posts

---

## Development

### Prerequisites

- Python 3.11+
- Docker (for container testing)

### Local Setup

git clone https://github.com/kitradrago/bluesky-crosspost.git
cd bluesky-crosspost
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python src/main.py

### Project Layout

bluesky-crosspost/
├── src/
│   ├── main.py               # Entry point and CrosspostManager
│   ├── config.py             # Configuration loader (python-dotenv)
│   ├── webui.py              # aiohttp web server and management UI
│   ├── bluesky_client.py     # atproto Bluesky API client
│   ├── telegram_client.py    # Telegram integration
│   ├── discord_client.py     # Discord integration
│   ├── furaffinity_client.py # FurAffinity integration
│   └── templates/
│       └── index.html        # Web UI dashboard
├── .env.example              # Template for environment variables
├── docker-compose.yml
├── Dockerfile
└── unraid-docker-template.xml

### Architecture

CrosspostManager
├── BlueskyClient (atproto)   — polls for new posts
├── TelegramClient            — forwards posts via Bot API
├── DiscordClient (discord.py)— forwards posts via bot
├── FurAffinityClient         — forwards posts via web scraping
└── WebUI (aiohttp)           — management interface on port 2759

Configuration is loaded from /config/.env (persistent volume) at startup, with Docker environment variables as fallback. Settings saved through the web UI are written to /config/.env and applied after a container restart.

---

## Security Notes

- Never commit your .env file with real credentials to version control. It is listed in .gitignore.
- Use app passwords, not your main Bluesky login password.
- Change the default admin / admin credentials immediately after first login.
- Admin passwords are encrypted with Fernet (AES-128-CBC) before being stored.
- Rotate bot tokens periodically and restrict bot permissions to the minimum needed.
- Keep FurAffinity credentials secure and confidential.

---

## License

This project is open source and available under the MIT License.

## Contributing

See CONTRIBUTING.md for guidelines on submitting issues and pull requests.
