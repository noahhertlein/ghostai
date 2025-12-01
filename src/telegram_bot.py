"""
Telegram bot for auto-publishing blog posts with notifications.
"""

import logging
import html
from typing import Optional, Callable

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from .config import get_config
from .gemini_client import GeminiClient, BlogPost
from .ghost_client import GhostClient
from .content_enricher import ContentEnricher

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for auto-publishing blog posts."""
    
    def __init__(self, on_generate_callback: Optional[Callable] = None):
        config = get_config()
        self.bot_token = config.telegram_bot_token
        self.authorized_user_id = config.telegram_user_id
        self.ghost_url = config.ghost_url
        
        # Clients
        self.gemini = GeminiClient()
        self.ghost = GhostClient()
        self.enricher = ContentEnricher()
        
        # External callback for scheduled generation
        self.on_generate_callback = on_generate_callback
        
        # Build the application
        self.app = Application.builder().token(self.bot_token).build()
        self._register_handlers()
    
    def _register_handlers(self):
        """Register command handlers."""
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("generate", self._cmd_generate))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("topics", self._cmd_topics))
    
    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot."""
        return user_id == self.authorized_user_id
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔ Unauthorized. This bot is private.")
            return
        
        await update.message.reply_text(
            "🤖 <b>Ghost Auto Blog Generator</b>\n\n"
            "I automatically generate and publish rich tech blog posts to your Ghost blog.\n\n"
            "📅 <b>Auto-posts:</b> 9 AM and 3 PM UTC daily\n"
            "📸 <b>Rich content:</b> Images + YouTube videos\n\n"
            "<b>Commands:</b>\n"
            "/generate - Manually publish a new post now\n"
            "/status - Check bot status\n"
            "/topics - See topic ideas\n"
            "/help - Show this help message",
            parse_mode='HTML'
        )
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        await update.message.reply_text(
            "📚 <b>How it works:</b>\n\n"
            "🤖 <b>Auto-Publish Mode</b>\n"
            "Rich posts are automatically generated and published:\n"
            "• 9:00 AM UTC - Morning post\n"
            "• 3:00 PM UTC - Afternoon post\n\n"
            "Each post includes:\n"
            "• 🖼️ Hero image + section images\n"
            "• 🎬 Relevant YouTube video embed\n"
            "• 📝 3-4 detailed sections\n\n"
            "You'll receive a notification after each post is published.\n\n"
            "📝 <b>Manual Publishing</b>\n"
            "Use /generate to create and publish a post immediately.\n\n"
            f"📍 <b>Blog:</b> {self.ghost_url}",
            parse_mode='HTML'
        )
    
    async def _cmd_generate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate command - create and auto-publish a new rich blog post."""
        if not self._is_authorized(update.effective_user.id):
            await update.message.reply_text("⛔ Unauthorized.")
            return
        
        await update.message.reply_text("🔄 Generating a new blog post topic...")
        
        try:
            # Get recent titles to avoid duplicates
            recent_titles = self.ghost.get_recent_titles(limit=20)
            
            # Generate topic
            topic = self.gemini.generate_topic(previous_topics=recent_titles)
            await update.message.reply_text(f"📝 Topic: <b>{html.escape(topic)}</b>\n\nGenerating full article...", parse_mode='HTML')
            
            # Generate full post
            blog_post = self.gemini.generate_blog_post(topic)
            await update.message.reply_text(f"📄 Generated {len(blog_post.sections)} sections\n\n🖼️ Finding images and video...")
            
            # Enrich with images and video
            enriched = self.enricher.enrich(blog_post)
            
            image_count = len(enriched.section_images) + (1 if enriched.hero_image else 0)
            video_status = "✅ Found" if enriched.video else "❌ None"
            
            await update.message.reply_text(f"🎨 Content enriched!\n• {image_count} images\n• Video: {video_status}\n\n📤 Publishing to Ghost...")
            
            # Prepare feature image data
            feature_image = enriched.hero_image.url if enriched.hero_image else None
            feature_image_alt = enriched.hero_image.alt_text if enriched.hero_image else None
            feature_image_caption = enriched.hero_image.get_attribution_html() if enriched.hero_image else None
            
            # Publish to Ghost with enriched content
            post_data = self.ghost.publish_post(
                blog_post,
                status='published',
                feature_image=feature_image,
                feature_image_alt=feature_image_alt,
                feature_image_caption=feature_image_caption,
                html_override=enriched.html_content
            )
            
            post_url = f"{self.ghost_url}/{blog_post.slug}/"
            hero_status = f"📸 by {enriched.hero_image.photographer_name}" if enriched.hero_image else "⚠️ No hero"
            video_info = f"🎬 {enriched.video.title[:40]}..." if enriched.video else "🎬 No video"
            tags_str = ", ".join(blog_post.tags)
            
            # Send success message
            await update.message.reply_text(
                f"✅ <b>Published Rich Post!</b>\n\n"
                f"<b>Title:</b> {html.escape(blog_post.title)}\n\n"
                f"<b>Sections:</b> {len(blog_post.sections)}\n"
                f"<b>Images:</b> {image_count} total\n"
                f"<b>Video:</b> {video_info}\n\n"
                f"<b>Tags:</b> {html.escape(tags_str)}\n\n"
                f"<b>URL:</b> {post_url}",
                parse_mode='HTML'
            )
            
            # Send hero image preview
            if enriched.hero_image:
                try:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=enriched.hero_image.thumb_url,
                        caption=f"🖼️ Hero: {hero_status}"
                    )
                except Exception:
                    pass
            
            logger.info(f"Manually published rich post: {blog_post.title}")
            
        except Exception as e:
            logger.error(f"Error generating post: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")
    
    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        try:
            # Test Ghost connection
            ghost_ok = self.ghost.test_connection()
            ghost_status = "✅ Connected" if ghost_ok else "❌ Failed"
            
            # Get recent posts
            recent = self.ghost.get_posts(limit=3)
            recent_list = "\n".join([f"  • {p['title'][:40]}..." for p in recent]) if recent else "  No posts found"
            
            await update.message.reply_text(
                f"📊 <b>Bot Status</b>\n\n"
                f"<b>Mode:</b> Auto-Publish ✨\n"
                f"<b>Schedule:</b> 9 AM & 3 PM UTC\n"
                f"<b>Content:</b> Rich (images + video)\n"
                f"<b>Ghost API:</b> {ghost_status}\n\n"
                f"<b>Recent posts:</b>\n{recent_list}",
                parse_mode='HTML'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error checking status: {str(e)}")
    
    async def _cmd_topics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /topics command - show topic ideas."""
        if not self._is_authorized(update.effective_user.id):
            return
        
        await update.message.reply_text("🎯 Generating 5 topic ideas...")
        
        try:
            recent_titles = self.ghost.get_recent_titles(limit=20)
            topics = []
            
            for i in range(5):
                topic = self.gemini.generate_topic(previous_topics=recent_titles + topics)
                topics.append(topic)
            
            topics_list = "\n".join([f"{i+1}. {t}" for i, t in enumerate(topics)])
            
            await update.message.reply_text(
                f"💡 <b>Topic Ideas:</b>\n\n{topics_list}\n\n"
                "Use /generate to create a post (topic will be auto-selected)",
                parse_mode='HTML'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Error generating topics: {str(e)}")
    
    def run(self):
        """Start the bot (blocking)."""
        logger.info("Starting Telegram bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
    
    async def run_async(self):
        """Start the bot asynchronously."""
        logger.info("Starting Telegram bot (async)...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    async def stop_async(self):
        """Stop the bot asynchronously."""
        logger.info("Stopping Telegram bot...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
