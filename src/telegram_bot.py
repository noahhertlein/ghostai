"""
Telegram bot for blog post approval workflow.
Sends draft posts for review and handles approve/reject actions.
"""

import asyncio
import logging
import html
from typing import Optional, Callable

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import get_config
from .gemini_client import GeminiClient, BlogPost
from .ghost_client import GhostClient
from .unsplash_client import UnsplashClient, UnsplashImage

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot for managing blog post approvals."""
    
    def __init__(self, on_generate_callback: Optional[Callable] = None):
        config = get_config()
        self.bot_token = config.telegram_bot_token
        self.authorized_user_id = config.telegram_user_id
        self.ghost_url = config.ghost_url
        
        # Clients
        self.gemini = GeminiClient()
        self.ghost = GhostClient()
        self.unsplash = UnsplashClient()
        
        # Pending posts awaiting approval (message_id -> (BlogPost, UnsplashImage))
        self.pending_posts: dict[int, tuple[BlogPost, UnsplashImage]] = {}
        
        # External callback for scheduled generation
        self.on_generate_callback = on_generate_callback
        
        # Build the application
        self.app = Application.builder().token(self.bot_token).build()
        self._register_handlers()
    
    def _register_handlers(self):
        """Register command and callback handlers."""
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("help", self._cmd_help))
        self.app.add_handler(CommandHandler("generate", self._cmd_generate))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("topics", self._cmd_topics))
        self.app.add_handler(CallbackQueryHandler(self._handle_callback))
    
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
            "I automatically generate and publish tech blog posts to your Ghost blog.\n\n"
            "📅 <b>Auto-posts:</b> 9 AM and 3 PM UTC daily\n\n"
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
            "Posts are automatically generated and published:\n"
            "• 9:00 AM UTC - Morning post\n"
            "• 3:00 PM UTC - Afternoon post\n\n"
            "You'll receive a notification after each post is published.\n\n"
            "📝 <b>Manual Publishing</b>\n"
            "Use /generate to create and publish a post immediately.\n\n"
            f"📍 <b>Blog:</b> {self.ghost_url}",
            parse_mode='HTML'
        )
    
    async def _cmd_generate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /generate command - create and auto-publish a new blog post."""
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
            
            # Fetch a relevant image from Unsplash
            await update.message.reply_text("🖼️ Finding a perfect image...")
            image = self.unsplash.get_image_for_topic(topic, blog_post.image_keywords)
            
            # Auto-publish
            await update.message.reply_text("📤 Publishing to Ghost...")
            
            # Prepare image data
            feature_image = image.url if image else None
            feature_image_alt = image.alt_text if image else None
            feature_image_caption = image.get_attribution_html() if image else None
            
            # Publish to Ghost
            post_data = self.ghost.publish_post(
                blog_post,
                status='published',
                feature_image=feature_image,
                feature_image_alt=feature_image_alt,
                feature_image_caption=feature_image_caption
            )
            
            post_url = f"{self.ghost_url}/{blog_post.slug}/"
            image_status = f"📸 by {image.photographer_name}" if image else "⚠️ No image"
            tags_str = ", ".join(blog_post.tags)
            
            # Send success message
            await update.message.reply_text(
                f"✅ <b>Published Successfully!</b>\n\n"
                f"<b>Title:</b> {html.escape(blog_post.title)}\n\n"
                f"<b>Tags:</b> {html.escape(tags_str)}\n\n"
                f"<b>Image:</b> {image_status}\n\n"
                f"<b>URL:</b> {post_url}",
                parse_mode='HTML'
            )
            
            # Send image preview
            if image:
                try:
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=image.thumb_url,
                        caption=f"🖼️ Feature image"
                    )
                except Exception:
                    pass
            
            logger.info(f"Manually published post: {blog_post.title}")
            
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
    
    async def _send_draft_for_approval(self, chat_id: int, blog_post: BlogPost, 
                                        image: UnsplashImage, context: ContextTypes.DEFAULT_TYPE):
        """Send a draft post to Telegram for approval."""
        
        # Truncate content preview
        content_preview = blog_post.html_content[:500]
        # Strip HTML tags for preview
        import re
        content_preview = re.sub(r'<[^>]+>', '', content_preview)
        content_preview = html.escape(content_preview)
        
        tags_str = ", ".join(blog_post.tags)
        
        # Build image info
        image_info = "❌ No image found"
        if image:
            image_info = f"📸 by {image.photographer_name}"
        
        message_text = (
            f"📄 <b>NEW DRAFT FOR REVIEW</b>\n\n"
            f"<b>Title:</b> {html.escape(blog_post.title)}\n\n"
            f"<b>Slug:</b> {html.escape(blog_post.slug)}\n\n"
            f"<b>Meta:</b> {html.escape(blog_post.meta_description)}\n\n"
            f"<b>Tags:</b> {html.escape(tags_str)}\n\n"
            f"<b>Image:</b> {image_info}\n\n"
            f"<b>Preview:</b>\n{content_preview}...\n\n"
            f"─────────────────────"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve & Publish", callback_data="approve"),
                InlineKeyboardButton("❌ Reject", callback_data="reject"),
            ],
            [
                InlineKeyboardButton("🔄 Regenerate", callback_data="regenerate"),
                InlineKeyboardButton("🖼️ New Image", callback_data="new_image"),
            ]
        ])
        
        # Send image preview first if available
        if image:
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=image.thumb_url,
                    caption=f"🖼️ Feature image by {image.photographer_name}"
                )
            except Exception as e:
                logger.warning(f"Failed to send image preview: {e}")
        
        sent_message = await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        
        # Store pending post with image
        self.pending_posts[sent_message.message_id] = (blog_post, image)
        logger.info(f"Draft sent for approval: {blog_post.title} (msg_id: {sent_message.message_id})")
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button callbacks."""
        query = update.callback_query
        await query.answer()
        
        if not self._is_authorized(update.effective_user.id):
            await query.edit_message_text("⛔ Unauthorized.")
            return
        
        message_id = query.message.message_id
        pending = self.pending_posts.get(message_id)
        
        if not pending:
            await query.edit_message_text("❌ This draft has expired or was already processed.")
            return
        
        blog_post, image = pending
        action = query.data
        
        if action == "approve":
            await self._handle_approve(query, blog_post, image, message_id)
        elif action == "reject":
            await self._handle_reject(query, blog_post, message_id)
        elif action == "regenerate":
            await self._handle_regenerate(query, blog_post, message_id, context)
        elif action == "new_image":
            await self._handle_new_image(query, blog_post, message_id, context)
    
    async def _handle_approve(self, query, blog_post: BlogPost, image: UnsplashImage, message_id: int):
        """Handle approval of a blog post."""
        try:
            await query.edit_message_text(
                f"⏳ Publishing: <b>{html.escape(blog_post.title)}</b>...",
                parse_mode='HTML'
            )
            
            # Prepare image data for Ghost
            feature_image = None
            feature_image_alt = None
            feature_image_caption = None
            
            if image:
                feature_image = image.url
                feature_image_alt = image.alt_text
                feature_image_caption = image.get_attribution_html()
            
            # Publish to Ghost with feature image
            post_data = self.ghost.publish_post(
                blog_post, 
                status='published',
                feature_image=feature_image,
                feature_image_alt=feature_image_alt,
                feature_image_caption=feature_image_caption
            )
            post_url = f"{self.ghost_url}/{blog_post.slug}/"
            
            # Remove from pending
            del self.pending_posts[message_id]
            
            image_status = "✅ With feature image" if image else "⚠️ No image"
            
            await query.edit_message_text(
                f"✅ <b>Published successfully!</b>\n\n"
                f"<b>Title:</b> {html.escape(blog_post.title)}\n"
                f"<b>Image:</b> {image_status}\n"
                f"<b>URL:</b> {post_url}",
                parse_mode='HTML'
            )
            
            logger.info(f"Published post: {blog_post.title}")
            
        except Exception as e:
            logger.error(f"Error publishing post: {e}")
            await query.edit_message_text(
                f"❌ Failed to publish: {str(e)}\n\n"
                "The draft was not discarded. Please try again.",
                parse_mode='HTML'
            )
    
    async def _handle_reject(self, query, blog_post: BlogPost, message_id: int):
        """Handle rejection of a blog post."""
        # Remove from pending
        del self.pending_posts[message_id]
        
        await query.edit_message_text(
            f"🗑️ <b>Draft rejected and discarded.</b>\n\n"
            f"Title was: {html.escape(blog_post.title)}\n\n"
            "Use /generate to create a new post.",
            parse_mode='HTML'
        )
        
        logger.info(f"Rejected post: {blog_post.title}")
    
    async def _handle_regenerate(self, query, blog_post: BlogPost, message_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Handle regeneration request."""
        try:
            await query.edit_message_text("🔄 Regenerating article with same topic...")
            
            # Extract topic from title
            topic = blog_post.title.split(':')[-1].strip() if ':' in blog_post.title else blog_post.title
            
            # Generate new version
            new_post = self.gemini.generate_blog_post(topic)
            
            # Fetch new image
            image = self.unsplash.get_image_for_topic(topic, new_post.image_keywords)
            
            # Remove old pending
            del self.pending_posts[message_id]
            
            # Send new draft
            await self._send_draft_for_approval(query.message.chat_id, new_post, image, context)
            
        except Exception as e:
            logger.error(f"Error regenerating post: {e}")
            await query.edit_message_text(f"❌ Error regenerating: {str(e)}")
    
    async def _handle_new_image(self, query, blog_post: BlogPost, message_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Handle request for a new image."""
        try:
            await query.edit_message_text("🖼️ Finding a new image...")
            
            # Get a random new image
            image = self.unsplash.get_random_photo(blog_post.image_keywords[0] if blog_post.image_keywords else blog_post.title)
            
            # Remove old pending
            del self.pending_posts[message_id]
            
            # Send updated draft with new image
            await self._send_draft_for_approval(query.message.chat_id, blog_post, image, context)
            
        except Exception as e:
            logger.error(f"Error getting new image: {e}")
            await query.edit_message_text(f"❌ Error getting new image: {str(e)}")
    
    async def send_scheduled_draft(self):
        """Generate and send a scheduled draft. Called by the scheduler."""
        try:
            logger.info("Generating scheduled blog post...")
            
            # Get recent titles to avoid duplicates
            recent_titles = self.ghost.get_recent_titles(limit=20)
            
            # Generate topic and post
            topic = self.gemini.generate_topic(previous_topics=recent_titles)
            blog_post = self.gemini.generate_blog_post(topic)
            
            # Fetch a relevant image
            image = self.unsplash.get_image_for_topic(topic, blog_post.image_keywords)
            
            # Send for approval
            async with self.app:
                await self._send_draft_for_approval(
                    self.authorized_user_id,
                    blog_post,
                    image,
                    self.app
                )
            
            logger.info(f"Scheduled draft sent: {blog_post.title}")
            
        except Exception as e:
            logger.error(f"Error in scheduled generation: {e}")
            # Try to notify user of error
            try:
                async with self.app:
                    await self.app.bot.send_message(
                        chat_id=self.authorized_user_id,
                        text=f"❌ Scheduled post generation failed: {str(e)}"
                    )
            except Exception:
                pass
    
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

