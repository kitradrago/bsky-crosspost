# Main.py Source code

import asyncio
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Set, Dict, List

from config import Config
from bluesky_client import BlueskyClient
from telegram_client import TelegramClient
from discord_client import DiscordClient
from furaffinity_client import FurAffinityClient
from webui import WebUI, create_webui

# Ensure all required directories exist
def ensure_directories():
    """Create all necessary directories"""
    directories = [
        '/config',
        '/config/logs',
        '/config/data',
        '/config/data/certs',
        Config.FURAFFINITY_IMAGE_DIR,
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Ensured directory exists: {directory}")

# Create directories before logging
ensure_directories()

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/config/logs/crosspost.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class CrosspostManager:
    def __init__(self, webui: WebUI = None):
        Config.validate()
        
        # Initialize Bluesky only if credentials are configured
        self.bluesky = None
        if Config.BLUESKY_HANDLE and Config.BLUESKY_PASSWORD and not Config.BLUESKY_HANDLE.startswith('your_'):
            self.bluesky = BlueskyClient(Config.BLUESKY_HANDLE, Config.BLUESKY_PASSWORD)
            logger.info("✅ Bluesky client initialized")
        else:
            logger.warning("⚠️ Bluesky credentials not configured - configure through web UI to enable")
        
        # Only initialize Telegram if enabled AND properly configured
        self.telegram = None
        if Config.TELEGRAM_ENABLED and Config.TELEGRAM_BOT_TOKEN and Config.TELEGRAM_CHANNEL_ID:
            if not Config.TELEGRAM_BOT_TOKEN.startswith('your_'):
                try:
                    self.telegram = TelegramClient(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHANNEL_ID)
                    logger.info("✅ Telegram client initialized")
                except Exception as e:
                    logger.warning(f"❌ Failed to initialize Telegram: {e}")
        elif Config.TELEGRAM_ENABLED:
            logger.warning("⚠️ Telegram enabled but bot token or channel ID not configured")
        
        # Only initialize Discord if enabled AND properly configured
        self.discord = None
        if Config.DISCORD_ENABLED and Config.DISCORD_BOT_TOKEN and Config.DISCORD_CHANNEL_ID:
            if not Config.DISCORD_BOT_TOKEN.startswith('your_'):
                try:
                    self.discord = DiscordClient(Config.DISCORD_BOT_TOKEN, Config.DISCORD_CHANNEL_ID)
                    logger.info("✅ Discord client initialized")
                except Exception as e:
                    logger.warning(f"❌ Failed to initialize Discord: {e}")
        elif Config.DISCORD_ENABLED:
            logger.warning("⚠️ Discord enabled but bot token or channel ID not configured")
        
        # Only initialize FurAffinity if enabled AND properly configured
        self.furaffinity = None
        if Config.FURAFFINITY_ENABLED and Config.FURAFFINITY_USERNAME and Config.FURAFFINITY_PASSWORD:
            if not Config.FURAFFINITY_USERNAME.startswith('your_'):
                try:
                    self.furaffinity = FurAffinityClient(
                        Config.FURAFFINITY_USERNAME,
                        Config.FURAFFINITY_PASSWORD,
                        Config.SELENIUM_URL,
                    )
                    logger.info("✅ FurAffinity client initialized")
                except Exception as e:
                    logger.warning(f"❌ Failed to initialize FurAffinity: {e}")
        elif Config.FURAFFINITY_ENABLED:
            logger.warning("⚠️ FurAffinity enabled but username or password not configured")
        
        self.webui = webui
        
        self.processed_posts: Set[str] = self._load_processed_posts()
        self.initialized = False
        self.bluesky_connected = False
        
    def _load_processed_posts(self) -> Set[str]:
        """Load previously processed post URIs"""
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        
        if os.path.exists(Config.PROCESSED_POSTS_FILE):
            try:
                with open(Config.PROCESSED_POSTS_FILE, 'r') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"Failed to load processed posts: {e}")
        
        return set()
    
    def _save_processed_posts(self):
        """Save processed post URIs"""
        try:
            with open(Config.PROCESSED_POSTS_FILE, 'w') as f:
                json.dump(list(self.processed_posts), f)
        except Exception as e:
            logger.error(f"Failed to save processed posts: {e}")
    
    def _get_bluesky_post_url(self, uri: str) -> str:
        """Convert AT URI to Bluesky post URL"""
        parts = uri.split('/')
        if len(parts) >= 2:
            post_id = parts[-1]
            return f"https://bsky.app/profile/{self.bluesky.target_handle}/post/{post_id}"
        return f"https://bsky.app/profile/unknown"
    
    def _is_reply(self, post: dict) -> bool:
        """Check if a post is a reply (has reply_to field)"""
        return 'reply_to' in post and post['reply_to'] is not None
    
    def _has_images(self, post: dict) -> bool:
        """Check if a post has images embedded"""
        return 'images' in post and isinstance(post['images'], list) and len(post['images']) > 0
    
    async def initialize(self) -> bool:
        """Initialize all clients and load existing posts"""
        logger.info("Initializing CrosspostManager...")
        
        # Try to connect Bluesky if configured
        if self.bluesky:
            if not await self.bluesky.connect():
                logger.warning("⚠️ Bluesky connection failed - WebUI is still available for configuration")
                logger.warning("⚠️ Check your credentials and restart the container")
                self.bluesky_connected = False
                self.bluesky = None
            else:
                self.bluesky_connected = True
                logger.info("✅ Connected to Bluesky")
                
                # On first run, load posts from last 24 hours but don't post them
                if not self.processed_posts:
                    logger.info("First run detected - loading posts from last 24 hours without posting")
                    try:
                        initial_posts = await self.bluesky.get_recent_posts(limit=50, hours_back=24)
                        
                        for post in initial_posts:
                            self.processed_posts.add(post['uri'])
                        
                        self._save_processed_posts()
                        logger.info(f"Marked {len(initial_posts)} existing posts as processed")
                    except Exception as e:
                        logger.error(f"Error loading initial posts: {e}")
        else:
            logger.info("⚠️ Bluesky not configured - waiting for setup through web UI")
        
        # Connect Discord if available
        if self.discord:
            try:
                if not await self.discord.connect():
                    logger.warning("Discord bot failed to connect")
                    self.discord = None
            except Exception as e:
                logger.warning(f"Discord connection error: {e}")
                self.discord = None
        
        self.initialized = True
        logger.info("✅ CrosspostManager initialization complete")
        return True
    
    async def process_new_posts(self):
        """Check for new posts and cross-post them (excluding replies)"""
        if not self.bluesky_connected:
            return
        
        try:
            # Only get posts from the last hour to catch new posts
            posts = await self.bluesky.get_recent_posts(limit=50, hours_back=1)
            
            new_posts = [p for p in posts if p['uri'] not in self.processed_posts]
            
            if new_posts:
                logger.info(f"Found {len(new_posts)} new posts")
                
                for post in reversed(new_posts):  # Process in chronological order
                    self.processed_posts.add(post['uri'])
                    
                    # Skip replies - only cross-post original posts
                    if self._is_reply(post):
                        logger.info(f"Skipping reply from {post['author']}")
                        if self.webui:
                            self.webui.save_post_record(
                                post,
                                telegram_sent=False,
                                discord_sent=False,
                                furaffinity_sent=False,
                            )
                        continue
                    
                    await self._cross_post(post)
                
                self._save_processed_posts()
            else:
                logger.debug("No new posts found")
        
        except Exception as e:
            logger.error(f"Error processing posts: {e}")
    
    async def _cross_post(self, post: dict):
        """Cross-post to Telegram, Discord, and FurAffinity"""
        try:
            bluesky_url = self._get_bluesky_post_url(post['uri'])
            author = post.get('display_name') or post['author']
            text = post['text']
            has_images = self._has_images(post)
            
            logger.info(f"Cross-posting from {author}: {text[:50]}... (has_images: {has_images})")
            
            telegram_sent = False
            discord_sent = False
            furaffinity_sent = False
            
            # Send to Telegram
            if self.telegram:
                try:
                    telegram_sent = await self.telegram.send_post(text, author, bluesky_url)
                except Exception as e:
                    logger.error(f"Telegram send error: {e}")
            
            # Send to Discord
            if self.discord:
                try:
                    discord_sent = await self.discord.send_post(text, author, bluesky_url)
                except Exception as e:
                    logger.error(f"Discord send error: {e}")
            
            # Post to FurAffinity (auto-detect image or journal)
            if self.furaffinity:
                try:
                    # Determine submission type based on whether post has images
                    if has_images and Config.FURAFFINITY_DOWNLOAD_IMAGES:
                        # Post as image submission
                        logger.info(f"Post has images - attempting image submission to FurAffinity")
                        image_urls = post.get('images', [])
                        
                        for image_url in image_urls[:1]:  # Only submit first image
                            local_path = await self.furaffinity.download_image(image_url)
                            if local_path:
                                title = f"Cross-post from {author}"
                                description = f"{text}\n\n🔗 Original post: {bluesky_url}"
                                furaffinity_sent = await asyncio.get_event_loop().run_in_executor(
                                    None,
                                    self.furaffinity.post_image,
                                    local_path,
                                    title,
                                    description,
                                    Config.FURAFFINITY_SUBMISSION_CATEGORY,
                                    Config.FURAFFINITY_SUBMISSION_RATING,
                                )
                                break
                        
                        if not furaffinity_sent:
                            logger.warning(f"Image submission failed, falling back to journal")
                            journal_title = f"Cross-post from {author}"
                            journal_content = f"{text}\n\n🔗 Original post: {bluesky_url}"
                            furaffinity_sent = await asyncio.get_event_loop().run_in_executor(
                                None,
                                self.furaffinity.post_journal,
                                journal_title,
                                journal_content,
                            )
                    else:
                        # Post as journal (no images or image download disabled)
                        if has_images and not Config.FURAFFINITY_DOWNLOAD_IMAGES:
                            logger.info(f"Post has images but download is disabled - posting as journal")
                        else:
                            logger.info(f"Post has no images - posting as journal")
                        
                        journal_title = f"Cross-post from {author}"
                        journal_content = f"{text}\n\n🔗 Original post: {bluesky_url}"
                        furaffinity_sent = await asyncio.get_event_loop().run_in_executor(
                            None,
                            self.furaffinity.post_journal,
                            journal_title,
                            journal_content,
                        )
                except Exception as e:
                    logger.error(f"FurAffinity send error: {e}")
            
            # Record in history
            if self.webui:
                self.webui.save_post_record(
                    post,
                    telegram_sent=telegram_sent,
                    discord_sent=discord_sent,
                    furaffinity_sent=furaffinity_sent,
                )
        
        except Exception as e:
            logger.error(f"Error cross-posting: {e}")
            if self.webui:
                self.webui.save_post_record(
                    post,
                    telegram_sent=False,
                    discord_sent=False,
                    furaffinity_sent=False,
                    error=str(e),
                )
    
    async def run(self):
        """Main run loop"""
        await self.initialize()
        
        logger.info(f"Starting crosspost service with {Config.BLUESKY_CHECK_INTERVAL}s interval")
        
        try:
            while True:
                await self.process_new_posts()
                await asyncio.sleep(Config.BLUESKY_CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Shutdown signal received")
        except Exception as e:
            logger.error(f"Fatal error: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down...")
        
        if self.bluesky:
            try:
                await self.bluesky.disconnect()
            except Exception as e:
                logger.error(f"Bluesky close error: {e}")
        
        if self.telegram:
            try:
                await self.telegram.close()
            except Exception as e:
                logger.error(f"Telegram close error: {e}")
        
        if self.discord:
            try:
                await self.discord.disconnect()
            except Exception as e:
                logger.error(f"Discord close error: {e}")
        
        logger.info("Shutdown complete")

async def main():
    # Initialize WebUI using singleton
    webui = create_webui(Config, '/config/data')
    
    # Start WebUI in background
    asyncio.create_task(webui.start(Config.WEBUI_PORT))
    
    # Start main crosspost manager
    manager = CrosspostManager(webui)
    
    # Set cross-post callback for WebUI retries
   async def retry_callback(post_uri: str = None, services: list[str] = None, hours_back: int = None) -> dict:
    """Handle both retry requests and manual post checks"""
    try:
        # MANUAL CHECK MODE - search for posts in past N hours
        if hours_back is not None and post_uri is None:
            logger.info(f"🔍 Manual check initiated for last {hours_back} hours")
            
            if not manager.bluesky_connected:
                return {'error': 'Bluesky not connected', 'success': False}
            
            # Get recent posts from the specified time range
            posts = await manager.bluesky.get_recent_posts(limit=50, hours_back=hours_back)
            
            if not posts:
                logger.warning(f"⚠️  No posts found in the last {hours_back} hours")
                return {'success': True, 'posts_found': 0, 'message': f'No posts found in the last {hours_back} hours'}
            
            logger.info(f"✅ Found {len(posts)} posts in the last {hours_back} hours, processing...")
            
            processed_count = 0
            for post in reversed(posts):
                # Skip replies
                if manager._is_reply(post):
                    logger.info(f"⏭️  Skipping reply from {post['author']}")
                    continue
                
                # Skip already processed posts
                if post['uri'] in manager.processed_posts:
                    logger.debug(f"⏭️  Post already processed: {post['text'][:50]}...")
                    continue
                
                logger.info(f"📤 Processing new post from manual check: {post['text'][:50]}...")
                manager.processed_posts.add(post['uri'])
                await manager._cross_post(post)
                processed_count += 1
            
            manager._save_processed_posts()
            
            return {
                'success': True,
                'posts_found': len(posts),
                'posts_processed': processed_count,
                'message': f'Found {len(posts)} posts, processed {processed_count} new posts'
            }
        
        # RETRY MODE - retry specific post
        elif post_uri is not None:
            # Find the post in history
            posts = webui._load_posts_history()
            post_data = None
            for p in posts:
                if p['uri'] == post_uri:
                    post_data = p
                    break
            
            if not post_data:
                return {'error': 'Post not found', 'success': False}
            
            # Reconstruct minimal post object
            post = {
                'uri': post_data['uri'],
                'text': post_data['text'],
                'author': post_data['author'],
                'created_at': post_data['created_at'],
            }
            
            # Retry selected services
            results = {}
            if 'telegram' in services and manager.telegram:
                try:
                    results['telegram'] = await manager.telegram.send_post(post['text'], post['author'], manager._get_bluesky_post_url(post['uri']))
                except Exception as e:
                    logger.error(f"Telegram retry error: {e}")
                    results['telegram'] = False
            
            if 'discord' in services and manager.discord:
                try:
                    results['discord'] = await manager.discord.send_post(post['text'], post['author'], manager._get_bluesky_post_url(post['uri']))
                except Exception as e:
                    logger.error(f"Discord retry error: {e}")
                    results['discord'] = False
            
            if 'furaffinity' in services and manager.furaffinity:
                try:
                    journal_title = f"Cross-post from {post['author']}"
                    journal_content = f"{post['text']}\n\n🔗 Original post: {manager._get_bluesky_post_url(post['uri'])}"
                    results['furaffinity'] = await asyncio.get_event_loop().run_in_executor(
                        None,
                        manager.furaffinity.post_journal,
                        journal_title,
                        journal_content,
                    )
                except Exception as e:
                    logger.error(f"FurAffinity retry error: {e}")
                    results['furaffinity'] = False
            
            # Update webui records
            webui.update_post_record(
                post_uri,
                telegram_sent=results.get('telegram', post_data['telegram_sent']),
                discord_sent=results.get('discord', post_data['discord_sent']),
                furaffinity_sent=results.get('furaffinity', post_data['furaffinity_sent']),
            )
            
            logger.info(f"✅ Retry complete: {results}")
            return {'success': True, 'results': results}
        
        else:
            return {'error': 'Invalid request parameters', 'success': False}
    
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        return {'error': str(e), 'success': False}
        
        """Handle retry requests from WebUI"""
        try:
            # Find the post in history
            posts = webui._load_posts_history()
            post_data = None
            for p in posts:
                if p['uri'] == post_uri:
                    post_data = p
                    break
            
            if not post_data:
                return {'error': 'Post not found', 'success': False}
            
            # Reconstruct minimal post object
            post = {
                'uri': post_data['uri'],
                'text': post_data['text'],
                'author': post_data['author'],
                'created_at': post_data['created_at'],
            }
            
            # Retry selected services
            results = {}
            if 'telegram' in services and manager.telegram:
                try:
                    results['telegram'] = await manager.telegram.send_post(post['text'], post['author'], manager._get_bluesky_post_url(post['uri']))
                except Exception as e:
                    logger.error(f"Telegram retry error: {e}")
                    results['telegram'] = False
            
            if 'discord' in services and manager.discord:
                try:
                    results['discord'] = await manager.discord.send_post(post['text'], post['author'], manager._get_bluesky_post_url(post['uri']))
                except Exception as e:
                    logger.error(f"Discord retry error: {e}")
                    results['discord'] = False
            
            if 'furaffinity' in services and manager.furaffinity:
                try:
                    journal_title = f"Cross-post from {post['author']}"
                    journal_content = f"{post['text']}\n\n🔗 Original post: {manager._get_bluesky_post_url(post['uri'])}"
                    results['furaffinity'] = await asyncio.get_event_loop().run_in_executor(
                        None,
                        manager.furaffinity.post_journal,
                        journal_title,
                        journal_content,
                    )
                except Exception as e:
                    logger.error(f"FurAffinity retry error: {e}")
                    results['furaffinity'] = False
            
            # Update webui records
            webui.update_post_record(
                post_uri,
                telegram_sent=results.get('telegram', post_data['telegram_sent']),
                discord_sent=results.get('discord', post_data['discord_sent']),
                furaffinity_sent=results.get('furaffinity', post_data['furaffinity_sent']),
            )
            
            logger.info(f"✅ Retry complete: {results}")
            return {'success': True, 'results': results}
        except Exception as e:
            logger.error(f"Retry callback error: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    webui.set_cross_post_callback(retry_callback)
    
    await manager.run()

if __name__ == "__main__":
    asyncio.run(main())