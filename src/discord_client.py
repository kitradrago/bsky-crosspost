import logging
import discord
from discord.ext import commands
from typing import Optional

logger = logging.getLogger(__name__)

class DiscordClient:
    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = int(channel_id)
        self.bot: Optional[discord.Client] = None
        self.ready = False
    
    async def connect(self) -> bool:
        """Connect Discord bot"""
        try:
            intents = discord.Intents.default()
            intents.message_content = True
            
            self.bot = discord.Client(intents=intents)
            
            @self.bot.event
            async def on_ready():
                logger.info(f"Discord bot connected as {self.bot.user}")
                self.ready = True
            
            # Start the bot without blocking
            import asyncio
            asyncio.create_task(self.bot.start(self.bot_token))
            
            # Wait for bot to be ready (with timeout)
            timeout = 0
            while not self.ready and timeout < 30:
                await asyncio.sleep(0.5)
                timeout += 0.5
            
            return self.ready
        except Exception as e:
            logger.error(f"Failed to connect Discord bot: {e}")
            return False
    
    async def send_post(self, text: str, author: str, bluesky_url: str) -> bool:
        """Send a post to Discord channel"""
        try:
            if not self.ready or not self.bot:
                logger.error("Discord bot not ready")
                return False
            
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                logger.error(f"Could not find Discord channel {self.channel_id}")
                return False
            
            message = self._format_message(text, author, bluesky_url)
            await channel.send(message)
            logger.info(f"Sent post to Discord from {author}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to Discord: {e}")
            return False
    
    def _format_message(self, text: str, author: str, bluesky_url: str) -> str:
        """Format message for Discord"""
        message = f"**{author}**\n\n{text}\n\n"
        message += f"[View on Bluesky]({bluesky_url})"
        return message
    
    async def disconnect(self):
        """Disconnect Discord bot"""
        if self.bot:
            await self.bot.close()
            logger.info("Discord bot disconnected")