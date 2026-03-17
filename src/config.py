import os
from dotenv import load_dotenv

# Load from /config/.env if it exists (takes priority)
if os.path.exists('/config/.env'):
    load_dotenv('/config/.env', override=True)
else:
    # Otherwise load from .env in current directory (for development)
    load_dotenv(override=True)

class Config:
    # Bluesky - read from .env, then env vars, then defaults
    BLUESKY_HANDLE = os.getenv('BLUESKY_HANDLE', '')
    BLUESKY_PASSWORD = os.getenv('BLUESKY_PASSWORD', '')
    BLUESKY_TARGET_HANDLE = os.getenv('BLUESKY_TARGET_HANDLE', '')
    BLUESKY_CHECK_INTERVAL = int(os.getenv('BLUESKY_CHECK_INTERVAL', '300'))
    
    # Telegram
    TELEGRAM_ENABLED = os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true'
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID', '')
    
    # Discord
    DISCORD_ENABLED = os.getenv('DISCORD_ENABLED', 'false').lower() == 'true'
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', '')
    DISCORD_CHANNEL_ID = os.getenv('DISCORD_CHANNEL_ID', '')

    # FurAffinity
    FURAFFINITY_ENABLED = os.getenv('FURAFFINITY_ENABLED', 'false').lower() == 'true'
    FURAFFINITY_USERNAME = os.getenv('FURAFFINITY_USERNAME', '')
    FURAFFINITY_PASSWORD = os.getenv('FURAFFINITY_PASSWORD', '')
    FURAFFINITY_SUBMISSION_TYPE = os.getenv('FURAFFINITY_SUBMISSION_TYPE', 'journal')  # 'journal' or 'image'
    FURAFFINITY_SUBMISSION_CATEGORY = os.getenv('FURAFFINITY_SUBMISSION_CATEGORY', '1')  # 1 = Artwork/Digital
    FURAFFINITY_SUBMISSION_RATING = os.getenv('FURAFFINITY_SUBMISSION_RATING', 'general')  # general, mature, adult
    FURAFFINITY_DOWNLOAD_IMAGES = os.getenv('FURAFFINITY_DOWNLOAD_IMAGES', 'false').lower() == 'true'
    FURAFFINITY_IMAGE_DIR = os.getenv('FURAFFINITY_IMAGE_DIR', '/config/data/fa_images')
    SELENIUM_URL = os.getenv('SELENIUM_URL', 'http://selenium:4444/wd/hub')
    
    # Admin
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
    
    # Application
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    DATA_DIR = os.getenv('DATA_DIR', '/config/data')
    LOG_DIR = os.getenv('LOG_DIR', '/config/logs')
    WEBUI_PORT = int(os.getenv('WEBUI_PORT', '2759'))
    
    # Derived paths
    PROCESSED_POSTS_FILE = os.path.join(DATA_DIR, 'processed_posts.json')
    
    @staticmethod
    def validate():
        """Validate required configuration"""
        if not Config.ADMIN_USERNAME or not Config.ADMIN_PASSWORD:
            raise ValueError("ADMIN_USERNAME and ADMIN_PASSWORD are required")