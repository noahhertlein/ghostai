"""
Main entry point for Ghost Auto Blog Generator.
Runs the Telegram bot with scheduled post generation.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import get_config
from .telegram_bot import TelegramBot
from .ghost_client import GhostClient
from .gemini_client import GeminiClient

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
    
    async def generate_and_send_draft(self):
        """Generate a new blog post and send it for approval via Telegram."""
        try:
            logger.info("Starting scheduled blog post generation...")
            
            # Initialize clients
            gemini = GeminiClient()
            ghost = GhostClient()
            
            # Get recent titles to avoid duplicates
            recent_titles = ghost.get_recent_titles(limit=20)
            logger.info(f"Found {len(recent_titles)} recent posts")
            
            # Generate topic
            topic = gemini.generate_topic(previous_topics=recent_titles)
            logger.info(f"Generated topic: {topic}")
            
            # Generate full blog post
            blog_post = gemini.generate_blog_post(topic)
            logger.info(f"Generated blog post: {blog_post.title}")
            
            # Send draft via Telegram for approval
            await self.bot.app.bot.send_message(
                chat_id=self.config.telegram_user_id,
                text=f"🔔 <b>Scheduled Post Ready!</b>\n\nGenerating draft for: {topic}",
                parse_mode='HTML'
            )
            
            # Use the bot's method to send draft
            await self.bot._send_draft_for_approval(
                self.config.telegram_user_id,
                blog_post,
                self.bot.app
            )
            
            logger.info("Scheduled draft sent successfully")
            
        except Exception as e:
            logger.error(f"Error in scheduled generation: {e}", exc_info=True)
            
            # Notify user of failure
            try:
                await self.bot.app.bot.send_message(
                    chat_id=self.config.telegram_user_id,
                    text=f"❌ <b>Scheduled generation failed:</b>\n{str(e)}",
                    parse_mode='HTML'
                )
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")
    
    def setup_scheduler(self):
        """Set up the scheduled job for automatic post generation."""
        hours = self.config.post_schedule_hours
        
        # Schedule the job
        self.scheduler.add_job(
            self.generate_and_send_draft,
            trigger=IntervalTrigger(hours=hours),
            id='generate_blog_post',
            name=f'Generate blog post every {hours} hours',
            next_run_time=datetime.now() + timedelta(hours=hours),  # First run after interval
            replace_existing=True,
        )
        
        logger.info(f"Scheduled automatic post generation every {hours} hours")
    
    async def startup(self):
        """Initialize and start all components."""
        logger.info("=" * 50)
        logger.info("Ghost Auto Blog Generator Starting...")
        logger.info("=" * 50)
        
        # Validate configuration
        logger.info(f"Ghost URL: {self.config.ghost_url}")
        logger.info(f"Gemini Model: {self.config.gemini_model}")
        logger.info(f"Schedule: Every {self.config.post_schedule_hours} hours")
        
        # Test Ghost connection
        ghost = GhostClient()
        if ghost.test_connection():
            logger.info("✓ Ghost API connection verified")
        else:
            logger.warning("⚠ Ghost API connection failed - check credentials")
        
        # Start the scheduler
        self.setup_scheduler()
        self.scheduler.start()
        logger.info("✓ Scheduler started")
        
        # Start the Telegram bot
        await self.bot.run_async()
        logger.info("✓ Telegram bot started")
        
        self.running = True
        logger.info("=" * 50)
        logger.info("Bot is running! Send /start to @NohatekGhostBot")
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

