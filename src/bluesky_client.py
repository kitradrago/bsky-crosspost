import logging
from atproto import Client
import asyncio
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from config import Config

logger = logging.getLogger(__name__)

class BlueskyClient:
    def __init__(self, handle: str, password: str):
        self.handle = handle
        self.password = password
        self.client: Optional[Client] = None
        self.user_did = None
        self.target_handle = Config.BLUESKY_TARGET_HANDLE
        
    async def connect(self) -> bool:
        """Connect to Bluesky"""
        try:
            logger.info(f"🔐 Attempting to connect to Bluesky as {self.handle}...")
            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(
                None,
                lambda: Client()
            )
            
            logger.info(f"🔑 Logging in with handle: {self.handle}")
            await loop.run_in_executor(
                None,
                lambda: self.client.login(self.handle, self.password)
            )
            
            self.user_did = self.client.me.did
            logger.info(f"✅ Successfully connected to Bluesky as {self.handle}")
            logger.info(f"📌 User DID: {self.user_did}")
            logger.info(f"👁️  Monitoring account: {self.target_handle}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Bluesky: {e}", exc_info=True)
            logger.error(f"❌ Check that your BLUESKY_HANDLE and BLUESKY_PASSWORD are correct")
            logger.error(f"❌ Make sure you're using an APP PASSWORD, not your login password")
            return False
    
    async def get_recent_posts(self, limit: int = 10, hours_back: int = 24) -> List[dict]:
        """Get recent posts from target account within last N hours"""
        try:
            if not self.client:
                logger.error("❌ Bluesky client not initialized - must call connect() first")
                return []
            
            logger.debug(f"🔍 Attempting to fetch up to {limit} posts from {self.target_handle} (within last {hours_back} hours)...")
            loop = asyncio.get_event_loop()
            
            # Get the target account's feed
            feed = await loop.run_in_executor(
                None,
                lambda: self.client.get_author_feed(self.target_handle, limit=limit)
            )
            
            logger.debug(f"📦 Received feed with {len(feed.feed)} total items from Bluesky API")
            
            posts = []
            # Use UTC timezone for consistent comparisons
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            logger.debug(f"⏰ Cutoff time (UTC): {cutoff_time}")
            
            for idx, post in enumerate(feed.feed):
                try:
                    logger.debug(f"📄 Processing item {idx + 1}/{len(feed.feed)}")
                    
                    # Check if post has required attributes
                    if not hasattr(post.post, 'record'):
                        logger.debug(f"   ⏭️  Skipping - no record attribute")
                        continue
                    
                    if not hasattr(post.post.record, 'text'):
                        logger.debug(f"   ⏭️  Skipping - no text attribute")
                        continue
                    
                    # Check if post is from the target account
                    post_author = post.post.author.handle
                    if post_author != self.target_handle:
                        logger.debug(f"   ⏭️  Skipping - from {post_author}, not {self.target_handle}")
                        continue
                    
                    # Parse the created_at timestamp
                    created_at = post.post.record.created_at
                    
                    # Convert to timezone-aware datetime if needed
                    if isinstance(created_at, str):
                        # Parse ISO format string
                        post_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        # If it's a datetime object, ensure it has timezone info
                        if created_at.tzinfo is None:
                            post_time = created_at.replace(tzinfo=timezone.utc)
                        else:
                            post_time = created_at
                    
                    logger.debug(f"   📅 Post created at: {post_time}")
                    
                    # Only include posts from the last N hours
                    if post_time >= cutoff_time:
                        # Check if this is a reply
                        reply_to = None
                        is_reply = False
                        if hasattr(post.post.record, 'reply') and post.post.record.reply:
                            reply_to = post.post.record.reply
                            is_reply = True
                        
                        post_text = post.post.record.text[:60] + "..." if len(post.post.record.text) > 60 else post.post.record.text
                        logger.info(f"✅ Found new post: {post_text} {'(REPLY)' if is_reply else ''}")
                        
                        post_data = {
                            'uri': post.post.uri,
                            'cid': post.post.cid,
                            'text': post.post.record.text,
                            'created_at': str(created_at),
                            'author': post.post.author.handle,
                            'display_name': post.post.author.display_name,
                            'reply_to': reply_to,
                        }
                        posts.append(post_data)
                    else:
                        logger.debug(f"   ⏭️  Skipping - post too old (created: {post_time}, cutoff: {cutoff_time})")
                
                except Exception as e:
                    logger.warning(f"   ⚠️  Error processing item {idx + 1}: {e}", exc_info=False)
                    continue
            
            if len(posts) == 0:
                logger.warning(f"⚠️  Retrieved 0 posts from {self.target_handle}")
                logger.warning(f"⚠️  This could mean:")
                logger.warning(f"   - No new posts in the last {hours_back} hours")
                logger.warning(f"   - All recent posts are replies (which we skip)")
                logger.warning(f"   - Target account handle is wrong")
            else:
                logger.info(f"✅ Successfully retrieved {len(posts)} recent posts from {self.target_handle}")
            
            return posts
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent posts: {e}", exc_info=True)
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Target handle: {self.target_handle}")
            return []
    
    async def disconnect(self):
        """Disconnect from Bluesky"""
        try:
            self.client = None
            logger.info("✅ Disconnected from Bluesky")
        except Exception as e:
            logger.error(f"Error disconnecting from Bluesky: {e}")