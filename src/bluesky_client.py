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
            
            logger.info(f"🔍 Fetching posts from {self.target_handle} (limit: {limit}, within last {hours_back} hours)...")
            loop = asyncio.get_event_loop()
            
            # Get the target account's feed
            feed = await loop.run_in_executor(
                None,
                lambda: self.client.get_author_feed(self.target_handle, limit=limit)
            )
            
            logger.info(f"📦 Received {len(feed.feed)} items from Bluesky API for {self.target_handle}")
            
            posts = []
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            logger.info(f"⏰ Looking for posts created after: {cutoff_time.isoformat()}")
            
            filtered_out = {
                'no_record': 0,
                'no_text': 0,
                'wrong_author': 0,
                'too_old': 0,
                'total_kept': 0
            }
            
            for idx, post in enumerate(feed.feed):
                try:
                    # Check if post has required attributes
                    if not hasattr(post.post, 'record'):
                        filtered_out['no_record'] += 1
                        logger.debug(f"  Item {idx + 1}: ❌ No record attribute")
                        continue
                    
                    if not hasattr(post.post.record, 'text'):
                        filtered_out['no_text'] += 1
                        logger.debug(f"  Item {idx + 1}: ❌ No text attribute")
                        continue
                    
                    # Check if post is from the target account
                    post_author = post.post.author.handle
                    if post_author != self.target_handle:
                        filtered_out['wrong_author'] += 1
                        logger.debug(f"  Item {idx + 1}: ❌ From {post_author} (not {self.target_handle})")
                        continue
                    
                    # Parse the created_at timestamp
                    created_at = post.post.record.created_at
                    
                    # Convert to timezone-aware datetime if needed
                    if isinstance(created_at, str):
                        post_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        if created_at.tzinfo is None:
                            post_time = created_at.replace(tzinfo=timezone.utc)
                        else:
                            post_time = created_at
                    
                    # Only include posts from the last N hours
                    if post_time < cutoff_time:
                        filtered_out['too_old'] += 1
                        age_hours = (datetime.now(timezone.utc) - post_time).total_seconds() / 3600
                        logger.debug(f"  Item {idx + 1}: ❌ Too old ({age_hours:.1f} hours ago)")
                        continue
                    
                    # Check if this is a reply
                    reply_to = None
                    is_reply = False
                    if hasattr(post.post.record, 'reply') and post.post.record.reply:
                        reply_to = post.post.record.reply
                        is_reply = True
                    
                    post_text = post.post.record.text[:60] + "..." if len(post.post.record.text) > 60 else post.post.record.text
                    
                    filtered_out['total_kept'] += 1
                    logger.info(f"  Item {idx + 1}: ✅ ACCEPTED - {post_text} {'(REPLY)' if is_reply else '(ORIGINAL)'}")
                    
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
                
                except Exception as e:
                    logger.warning(f"  Item {idx + 1}: ⚠️  Error processing: {e}")
                    continue
            
            # Summary
            logger.info(f"")
            logger.info(f"📊 FILTER SUMMARY:")
            logger.info(f"   Total items received: {len(feed.feed)}")
            logger.info(f"   ❌ No record: {filtered_out['no_record']}")
            logger.info(f"   ❌ No text: {filtered_out['no_text']}")
            logger.info(f"   ❌ Wrong author: {filtered_out['wrong_author']}")
            logger.info(f"   ❌ Too old (>  {hours_back}h): {filtered_out['too_old']}")
            logger.info(f"   ✅ ACCEPTED: {filtered_out['total_kept']}")
            logger.info(f"")
            
            if len(posts) == 0:
                logger.warning(f"⚠️  No posts matched filters!")
            else:
                logger.info(f"✅ Returning {len(posts)} posts")
            
            return posts
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent posts: {e}", exc_info=True)
            return []
    
    async def disconnect(self):
        """Disconnect from Bluesky"""
        try:
            self.client = None
            logger.info("✅ Disconnected from Bluesky")
        except Exception as e:
            logger.error(f"Error disconnecting from Bluesky: {e}")