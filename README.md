# 🚀 Bluesky Crosspost Manager

Automatically monitor a Bluesky account and crosspost to **Telegram**, **Discord**, and **FurAffinity** with an easy-to-use web interface.

## Features

- 📱 **Web UI** - Configure everything through a beautiful web dashboard
- 🔍 **Manual Post Check** - Search and selectively crosspost old posts
- 📊 **Activity Log** - Track all posts and their crosspost status
- 🎛️ **Per-Service Control** - Enable/disable individual platforms
- 🔐 **Secure** - Passwords encrypted at rest, HTTPS web UI
- 🏗️ **Multi-Architecture** - Runs on amd64 (x86) and arm64 (Raspberry Pi, etc.)
- 📝 **Detailed Logging** - See exactly what's happening in real-time

## Supported Platforms

- **Telegram** - Posts messages to a Telegram channel
- **Discord** - Posts messages to a Discord channel  
- **FurAffinity** - Posts as journal entries (text) or image submissions

## How do I support you

If you would like to support me, please consider sending a donation to my GoFundMe for my medical needs. Its location here - https://www.gofundme.com/f/help-kitra-live-authentically

Future possible enhancements:

    Toggle whether you want self-replies crossposted as well, and to what services.
    Graphical representation of community engagement.
    Potentially incorporating a notification function for if community replies with a question or specific hashtags (i.e. #question)


## Installation

### Docker (Recommended)

docker run -d \
  --name bsky-crosspost \
  -p 2759:2759 \
  -v /path/to/config:/config \
  -e BLUESKY_HANDLE="your_handle.bsky.social" \
  -e BLUESKY_PASSWORD="your_app_password" \
  -e BLUESKY_TARGET_HANDLE="your_handle.bsky.social" \
  kitradrago/bsky-crosspost:latest

### Docker Compose

version: '3.8'

services:
  bsky-crosspost:
    image: kitradrago/bsky-crosspost:latest
    ports:
      - "2759:2759"
    volumes:
      - ./config:/config
    environment:
      - BLUESKY_HANDLE=your_handle.bsky.social
      - BLUESKY_PASSWORD=your_app_password
      - BLUESKY_TARGET_HANDLE=your_handle.bsky.social
      - LOG_LEVEL=INFO
    restart: unless-stopped

### Unraid

This application is available in the Unraid Community Applications store:
1. Go to **Apps** tab
2. Search for **Bluesky-Crosspost**
3. Click **Install**
4. Configure settings and start

## Configuration

### Web UI Setup

1. **Access the web UI:**
   - Navigate to https://your-server:2759
   - Default login: admin / admin
   - ⚠️ Change the password immediately!

2. **Configure Bluesky:**
   - Enter your Bluesky handle
   - Generate an app password at https://bsky.app/settings/app-passwords
   - Enter the handle to monitor (can be the same or different)

3. **Configure Services:**
   - Check the **Enable** checkbox for each service you want to use
   - Enter service credentials
   - Click **💾 Save Settings**
   - Click **Restart Now**

### Environment Variables

BLUESKY_HANDLE - Required - Your Bluesky handle (e.g., username.bsky.social)
BLUESKY_PASSWORD - Required - App password for your Bluesky account
BLUESKY_TARGET_HANDLE - Required - The Bluesky account to monitor (can be same as BLUESKY_HANDLE)
BLUESKY_CHECK_INTERVAL - Optional - Default: 300 - Seconds between checks (minimum: 10)
TELEGRAM_ENABLED - Optional - Default: false - Enable Telegram crossposting
TELEGRAM_BOT_TOKEN - Optional - Telegram bot token
TELEGRAM_CHANNEL_ID - Optional - Telegram channel ID (format: -1001234567890)
DISCORD_ENABLED - Optional - Default: false - Enable Discord crossposting
DISCORD_BOT_TOKEN - Optional - Discord bot token
DISCORD_CHANNEL_ID - Optional - Discord channel ID
FURAFFINITY_ENABLED - Optional - Default: false - Enable FurAffinity posting
FURAFFINITY_USERNAME - Optional - FurAffinity username
FURAFFINITY_PASSWORD - Optional - FurAffinity password
ADMIN_USERNAME - Optional - Default: admin - Web UI login username
ADMIN_PASSWORD - Optional - Default: admin - Web UI login password (encrypted)
LOG_LEVEL - Optional - Default: INFO - Logging level: DEBUG, INFO, WARNING, ERROR

## Getting Credentials

### Bluesky App Password

1. Go to https://bsky.app/settings/app-passwords
2. Click **Create App Password**
3. Copy the generated password (⚠️ save it securely, you can't see it again)

### Telegram

1. Talk to @BotFather on Telegram
2. Create a new bot with /newbot
3. Copy the bot token
4. Create a Telegram channel and add your bot as admin
5. Get your channel ID (format: -1001234567890)

### Discord

1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to **Bot** section and copy the token
4. Create a Discord server and add the bot with permissions to post messages
5. Get your channel ID (right-click channel → Copy ID)

### FurAffinity

Simply use your FurAffinity username and password. The app logs in securely.

## Usage

### Automatic Posting

Once configured, the app automatically:
1. Checks your Bluesky account every 5 minutes (configurable)
2. Finds new posts
3. Skips replies (only posts original content)
4. Posts to enabled platforms

### Manual Checking

1. Go to **🔍 Manual Check** tab
2. Enter hours to search (1-168)
3. Click **🔍 Search Posts**
4. Select which posts you want to crosspost
5. Click **📤 Crosspost Selected**

### Monitoring

- **📊 Activity tab** - View statistics and post history
- **📋 Logs tab** - Real-time logs of all activities
- **⚙️ Setup tab** - Change configuration anytime

## Data Storage

All data is stored in the /config volume:
- .env - Configuration
- posts_history.json - Post history and crosspost status
- processed_posts.json - List of already-processed posts
- logs/ - Application logs
- data/ - Encryption keys and certificates

## Troubleshooting

### Services not initialized?

- Make sure to **check the Enable checkbox** for each service
- Click **💾 Save Settings**
- Click **Restart Now** on the notification banner

### Posts not being crossposts?

1. Check the **📋 Logs** tab for errors
2. Verify credentials are correct in **⚙️ Setup** tab
3. Make sure services are **Enabled**
4. Check that the Bluesky account is accessible

### Can't access web UI?

- Make sure port 2759 is open: https://your-server:2759
- Check docker logs: docker logs bsky-crosspost
- Try accessing via IP instead of hostname

### Wrong password?

- Default: admin / admin
- Reset by accessing the **🔐 Admin** tab and updating credentials
- Click **Restart Now**

## Logs

View logs in the web UI (**📋 Logs** tab) or:

docker logs -f bsky-crosspost

docker inspect bsky-crosspost | grep LogPath

## Performance

- Minimal CPU/memory usage (~50-100MB)
- Single thread for checking, async for posting
- Default check interval: 5 minutes
- Processes posts in chronological order

## Security

- ✅ HTTPS with self-signed certificates
- ✅ Passwords encrypted at rest using Fernet
- ✅ No external API calls except to social networks
- ✅ Admin login required for configuration
- ⚠️ Change default admin password on first login!

## Limitations

- Manual check searches maximum 168 hours (7 days)
- Only posts original content (skips replies)
- Telegram/Discord: text only (links preserved)
- FurAffinity: journal entries or single image submissions

## License

MIT License - See LICENSE file

## Support

- 📖 **Issues:** https://github.com/kitradrago/bsky-crosspost/issues
- 💬 **Discussions:** https://github.com/kitradrago/bsky-crosspost/discussions

## Changelog

### v1.0.2 (Latest)

- Added Manual Post Check feature
- Added per-service Enable/Disable toggles
- Improved logging and error messages
- Multi-architecture Docker builds (amd64 + arm64)
- All startup posts now saved to activity log

### v1.0.1

- Initial release with core functionality

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

**Made with ❤️ for the furry community**