"""
YouTube Data API client for finding relevant videos to embed in blog posts.
"""

import logging
from typing import Optional
from dataclasses import dataclass

import requests

from .config import get_config

logger = logging.getLogger(__name__)

YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3"


@dataclass
class YouTubeVideo:
    """Represents a YouTube video for embedding."""
    video_id: str
    title: str
    channel_title: str
    thumbnail_url: str
    
    @property
    def embed_url(self) -> str:
        """Get the embed URL for the video."""
        return f"https://www.youtube.com/embed/{self.video_id}"
    
    @property
    def watch_url(self) -> str:
        """Get the watch URL for the video."""
        return f"https://www.youtube.com/watch?v={self.video_id}"
    
    def get_embed_html(self) -> str:
        """Generate Ghost-compatible HTML embed code."""
        return (
            f'<figure class="kg-card kg-embed-card">'
            f'<iframe width="560" height="315" '
            f'src="{self.embed_url}" '
            f'title="{self.title}" '
            f'frameborder="0" '
            f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
            f'allowfullscreen></iframe>'
            f'<figcaption>{self.title} - {self.channel_title}</figcaption>'
            f'</figure>'
        )


class YouTubeClient:
    """Client for searching YouTube videos."""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.youtube_api_key
    
    def search_videos(self, query: str, max_results: int = 5) -> list[YouTubeVideo]:
        """
        Search for videos matching a query.
        
        Args:
            query: Search terms
            max_results: Maximum number of results (1-50)
        
        Returns:
            List of YouTubeVideo objects
        """
        url = f"{YOUTUBE_API_URL}/search"
        params = {
            "key": self.api_key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": min(max_results, 50),
            "videoEmbeddable": "true",
            "safeSearch": "moderate",
            "relevanceLanguage": "en",
            "order": "relevance",
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            videos = []
            for item in data.get("items", []):
                snippet = item["snippet"]
                video = YouTubeVideo(
                    video_id=item["id"]["videoId"],
                    title=snippet["title"],
                    channel_title=snippet["channelTitle"],
                    thumbnail_url=snippet["thumbnails"]["high"]["url"],
                )
                videos.append(video)
            
            logger.info(f"Found {len(videos)} videos for query: {query}")
            return videos
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"YouTube API error: {e}")
            if e.response and e.response.status_code == 403:
                logger.error("YouTube API quota exceeded or invalid key")
            return []
        except Exception as e:
            logger.error(f"Error searching YouTube: {e}")
            return []
    
    def get_best_video(self, topic: str, keywords: list[str] = None) -> Optional[YouTubeVideo]:
        """
        Get the most relevant video for a blog topic.
        
        Args:
            topic: The blog post topic
            keywords: Optional additional keywords
        
        Returns:
            YouTubeVideo or None
        """
        # Build search query
        search_terms = [topic]
        if keywords:
            search_terms.extend(keywords[:2])
        
        # Add "tutorial" or "explained" for better educational content
        query = f"{' '.join(search_terms)} tutorial explained"
        
        videos = self.search_videos(query, max_results=3)
        
        if videos:
            # Return the first (most relevant) video
            video = videos[0]
            logger.info(f"Selected video: {video.title}")
            return video
        
        # Fallback: try simpler search
        videos = self.search_videos(topic, max_results=3)
        if videos:
            return videos[0]
        
        logger.warning(f"No video found for topic: {topic}")
        return None

