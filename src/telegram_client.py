import logging
from telegram import Bot
from telegram.error import TelegramError
import asyncio

logger = logging.getLogger(__name__)

class TelegramClient:
    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.bot = Bot(token=bot_token)
    
    async def send_post(self, text: str, author: str, bluesky_url: str) -> bool:
        """Send a post to Telegram channel"""
        try:
            message = self._format_message(text, author, bluesky_url)
            
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode='HTML'
            )
            logger.info(f"Sent post to Telegram from {author}")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send message to Telegram: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending to Telegram: {e}")
            return False
    
    def _format_message(self, text: str, author: str, bluesky_url: str) -> str:
        """Format message for Telegram"""
        message = f"<b>{author}</b>\n\n{text}\n\n"
        message += f"<a href='{bluesky_url}'>View on Bluesky</a>"
        return message
    
    async def close(self):
        """Close the bot connection"""
        await self.bot.session.close()