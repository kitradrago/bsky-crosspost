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
            loop = asyncio.get_event_loop()
            self.client = await loop.run_in_executor(
                None,
                lambda: Client()
            )
            
            await loop.run_in_executor(
                None,
                lambda: self.client.login(self.handle, self.password)
            )
            
            self.user_did = self.client.me.did
            logger.info(f"Connected to Bluesky as {self.handle}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Bluesky: {e}")
            return False
    
    async def get_recent_posts(self, limit: int = 10, hours_back: int = 24) -> List[dict]:
        """Get recent posts from target account within last N hours"""
        try:
            loop = asyncio.get_event_loop()
            
            # Get the target account's feed
            feed = await loop.run_in_executor(
                None,
                lambda: self.client.get_author_feed(self.target_handle, limit=limit)
            )
            
            posts = []
            # Use UTC timezone for consistent comparisons
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            
            for post in feed.feed:
                if hasattr(post.post, 'record') and hasattr(post.post.record, 'text'):
                    # Check if post is from the target account
                    if post.post.author.handle != self.target_handle:
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
                    
                    # Only include posts from the last N hours
                    if post_time >= cutoff_time:
                        # Check if this is a reply
                        reply_to = None
                        if hasattr(post.post.record, 'reply') and post.post.record.reply:
                            reply_to = post.post.record.reply
                        
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
            
            logger.info(f"Retrieved {len(posts)} recent posts from {self.target_handle}")
            return posts
        except Exception as e:
            logger.error(f"Failed to get recent posts: {e}")
            return []
    
    async def disconnect(self):
        """Disconnect from Bluesky"""
        self.client = None
        logger.info("Disconnected from Bluesky")