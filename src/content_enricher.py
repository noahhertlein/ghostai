"""
Content enricher that adds images and videos to blog posts.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .gemini_client import BlogPost, BlogSection
from .unsplash_client import UnsplashClient, UnsplashImage
from .youtube_client import YouTubeClient, YouTubeVideo

logger = logging.getLogger(__name__)


@dataclass
class EnrichedContent:
    """Blog post content enriched with media."""
    html_content: str  # Full HTML with embedded images and video
    hero_image: Optional[UnsplashImage]
    section_images: list[UnsplashImage]
    video: Optional[YouTubeVideo]


class ContentEnricher:
    """Enriches blog posts with images and videos."""
    
    def __init__(self):
        self.unsplash = UnsplashClient()
        self.youtube = YouTubeClient()
    
    def enrich(self, blog_post: BlogPost) -> EnrichedContent:
        """
        Enrich a blog post with images and video.
        
        Args:
            blog_post: The generated blog post
        
        Returns:
            EnrichedContent with full HTML and media references
        """
        logger.info(f"Enriching blog post: {blog_post.title}")
        
        # Fetch hero image
        hero_image = self.unsplash.get_image_for_topic(
            blog_post.title, 
            blog_post.image_keywords
        )
        
        # Fetch images for each section
        section_images = []
        for section in blog_post.sections:
            image = self.unsplash.get_image_for_topic(
                section.heading,
                [section.image_keyword]
            )
            section_images.append(image)  # May be None
        
        # Fetch YouTube video
        video = self.youtube.get_best_video(
            blog_post.title,
            blog_post.video_keywords
        )
        
        # Generate enriched HTML
        html_content = self._build_enriched_html(
            blog_post, 
            section_images, 
            video
        )
        
        return EnrichedContent(
            html_content=html_content,
            hero_image=hero_image,
            section_images=[img for img in section_images if img],
            video=video,
        )
    
    def _build_enriched_html(
        self, 
        blog_post: BlogPost, 
        section_images: list[Optional[UnsplashImage]],
        video: Optional[YouTubeVideo]
    ) -> str:
        """Build the full HTML content with embedded media."""
        parts = []
        
        # Introduction
        parts.append(blog_post.intro)
        
        # Add video after intro (if available)
        if video:
            parts.append(video.get_embed_html())
        
        # Sections with images
        for i, section in enumerate(blog_post.sections):
            # Section heading
            parts.append(f"<h2>{section.heading}</h2>")
            
            # Section image (if available)
            if i < len(section_images) and section_images[i]:
                image = section_images[i]
                parts.append(self._get_image_html(image, section.heading))
            
            # Section content
            parts.append(section.content)
        
        # Conclusion
        parts.append(blog_post.conclusion)
        
        return "\n\n".join(parts)
    
    def _get_image_html(self, image: UnsplashImage, alt_context: str) -> str:
        """Generate Ghost-compatible HTML for an image."""
        alt_text = image.alt_text or alt_context
        attribution = image.get_attribution_html()
        
        return (
            f'<figure class="kg-card kg-image-card kg-card-hascaption">'
            f'<img src="{image.url}" alt="{alt_text}" loading="lazy">'
            f'<figcaption>{attribution}</figcaption>'
            f'</figure>'
        )


