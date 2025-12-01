"""
Main entry point for Ghost Auto Blog Generator.
Runs the Telegram bot with scheduled post generation.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_config
from .telegram_bot import TelegramBot
from .ghost_client import GhostClient
from .gemini_client import GeminiClient
from .unsplash_client import UnsplashClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)


class BlogGenerator:
    """Main application class that coordinates all components."""
    
    def __init__(self):
        self.config = get_config()
        self.bot = TelegramBot()
        self.scheduler = AsyncIOScheduler()
        self.running = False
    
    async def generate_and_auto_publish(self):
        """Generate a new blog post and automatically publish it."""
        try:
            logger.info("Starting scheduled blog post generation...")
            
            # Initialize clients
            gemini = GeminiClient()
            ghost = GhostClient()
            unsplash = UnsplashClient()
            
            # Get recent titles to avoid duplicates
            recent_titles = ghost.get_recent_titles(limit=20)
            logger.info(f"Found {len(recent_titles)} recent posts")
            
            # Generate topic
            topic = gemini.generate_topic(previous_topics=recent_titles)
            logger.info(f"Generated topic: {topic}")
            
            # Generate full blog post
            blog_post = gemini.generate_blog_post(topic)
            logger.info(f"Generated blog post: {blog_post.title}")
            
            # Fetch a relevant image from Unsplash
            image = unsplash.get_image_for_topic(topic, blog_post.image_keywords)
            if image:
                logger.info(f"Found image by {image.photographer_name}")
            else:
                logger.warning("No image found for topic")
            
            # Prepare image data for Ghost
            feature_image = image.url if image else None
            feature_image_alt = image.alt_text if image else None
            feature_image_caption = image.get_attribution_html() if image else None
            
            # Auto-publish to Ghost
            post_data = ghost.publish_post(
                blog_post,
                status='published',
                feature_image=feature_image,
                feature_image_alt=feature_image_alt,
                feature_image_caption=feature_image_caption
            )
            
            post_url = f"{self.config.ghost_url}/{blog_post.slug}/"
            logger.info(f"Auto-published: {blog_post.title}")
            
            # Send notification to Telegram (no approval needed)
            image_status = f"📸 by {image.photographer_name}" if image else "⚠️ No image"
            tags_str = ", ".join(blog_post.tags)
            
            await self.bot.app.bot.send_message(
                chat_id=self.config.telegram_user_id,
                text=(
                    f"✅ <b>Auto-Published New Post!</b>\n\n"
                    f"<b>Title:</b> {blog_post.title}\n\n"
                    f"<b>Tags:</b> {tags_str}\n\n"
                    f"<b>Image:</b> {image_status}\n\n"
                    f"<b>URL:</b> {post_url}"
                ),
                parse_mode='HTML'
            )
            
            # Send image preview
            if image:
                try:
                    await self.bot.app.bot.send_photo(
                        chat_id=self.config.telegram_user_id,
                        photo=image.thumb_url,
                        caption=f"🖼️ Feature image for: {blog_post.title[:50]}..."
                    )
                except Exception:
                    pass
            
            logger.info("Auto-publish complete and notification sent")
            
        except Exception as e:
            logger.error(f"Error in scheduled generation: {e}", exc_info=True)
            
            # Notify user of failure
            try:
                await self.bot.app.bot.send_message(
                    chat_id=self.config.telegram_user_id,
                    text=f"❌ <b>Auto-publish failed:</b>\n{str(e)}",
                    parse_mode='HTML'
                )
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")
    
    def setup_scheduler(self):
        """Set up scheduled jobs for automatic post generation (2 per day)."""
        
        # Morning post at 9:00 AM UTC
        self.scheduler.add_job(
            self.generate_and_auto_publish,
            trigger=CronTrigger(hour=9, minute=0),
            id='morning_post',
            name='Morning blog post (9 AM)',
            replace_existing=True,
        )
        
        # Afternoon post at 3:00 PM (15:00) UTC
        self.scheduler.add_job(
            self.generate_and_auto_publish,
            trigger=CronTrigger(hour=15, minute=0),
            id='afternoon_post',
            name='Afternoon blog post (3 PM)',
            replace_existing=True,
        )
        
        logger.info("Scheduled automatic posts: 9 AM and 3 PM UTC")
    
    async def startup(self):
        """Initialize and start all components."""
        logger.info("=" * 50)
        logger.info("Ghost Auto Blog Generator Starting...")
        logger.info("=" * 50)
        
        # Validate configuration
        logger.info(f"Ghost URL: {self.config.ghost_url}")
        logger.info(f"Gemini Model: {self.config.gemini_model}")
        logger.info("Schedule: 9 AM and 3 PM UTC (2 posts per day)")
        
        # Test Ghost connection
        ghost = GhostClient()
        if ghost.test_connection():
            logger.info("✓ Ghost API connection verified")
        else:
            logger.warning("⚠ Ghost API connection failed - check credentials")
        
        # Start the scheduler
        self.setup_scheduler()
        self.scheduler.start()
        logger.info("✓ Scheduler started (auto-publish mode)")
        
        # Start the Telegram bot
        await self.bot.run_async()
        logger.info("✓ Telegram bot started")
        
        self.running = True
        logger.info("=" * 50)
        logger.info("Bot is running in AUTO-PUBLISH mode!")
        logger.info("Posts will publish automatically at 9 AM and 3 PM UTC")
        logger.info("=" * 50)
    
    async def shutdown(self):
        """Gracefully shut down all components."""
        logger.info("Shutting down...")
        self.running = False
        
        # Stop scheduler
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
        
        # Stop Telegram bot
        await self.bot.stop_async()
        logger.info("Telegram bot stopped")
        
        logger.info("Shutdown complete")
    
    async def run(self):
        """Main run loop."""
        await self.startup()
        
        # Keep running until interrupted
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()


async def main():
    """Entry point for the application."""
    app = BlogGenerator()
    
    # Handle shutdown signals
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("Received shutdown signal")
        app.running = False
    
    # Register signal handlers (Unix only)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass
    
    await app.run()


def run():
    """Synchronous entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()

