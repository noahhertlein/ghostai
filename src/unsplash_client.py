"""
Unsplash API client for fetching relevant images for blog posts.
"""

import logging
import requests
from typing import Optional
from dataclasses import dataclass

from .config import get_config

logger = logging.getLogger(__name__)

UNSPLASH_API_URL = "https://api.unsplash.com"


@dataclass
class UnsplashImage:
    """Represents an Unsplash image with attribution."""
    id: str
    url: str  # Regular size URL for feature image
    thumb_url: str  # Thumbnail for preview
    download_url: str  # URL to trigger download (for Unsplash tracking)
    photographer_name: str
    photographer_url: str
    unsplash_url: str  # Link to photo on Unsplash
    alt_text: str
    
    def get_attribution_html(self) -> str:
        """Generate proper Unsplash attribution HTML."""
        return (
            f'Photo by <a href="{self.photographer_url}?utm_source=ghost_auto_blog&utm_medium=referral">'
            f'{self.photographer_name}</a> on '
            f'<a href="{self.unsplash_url}?utm_source=ghost_auto_blog&utm_medium=referral">Unsplash</a>'
        )


class UnsplashClient:
    """Client for fetching images from Unsplash API."""
    
    def __init__(self):
        config = get_config()
        self.access_key = config.unsplash_access_key
        self.headers = {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept-Version": "v1"
        }
    
    def search_photos(self, query: str, per_page: int = 5) -> list[UnsplashImage]:
        """
        Search for photos matching a query.
        
        Args:
            query: Search terms
            per_page: Number of results (max 30)
        
        Returns:
            List of UnsplashImage objects
        """
        url = f"{UNSPLASH_API_URL}/search/photos"
        params = {
            "query": query,
            "per_page": per_page,
            "orientation": "landscape",  # Better for blog headers
            "content_filter": "high",  # Safe content only
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            images = []
            for photo in data.get("results", []):
                image = UnsplashImage(
                    id=photo["id"],
                    url=photo["urls"]["regular"],
                    thumb_url=photo["urls"]["thumb"],
                    download_url=photo["links"]["download_location"],
                    photographer_name=photo["user"]["name"],
                    photographer_url=photo["user"]["links"]["html"],
                    unsplash_url=photo["links"]["html"],
                    alt_text=photo.get("alt_description") or photo.get("description") or query,
                )
                images.append(image)
            
            logger.info(f"Found {len(images)} images for query: {query}")
            return images
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Unsplash API error: {e}")
            if e.response.status_code == 401:
                logger.error("Invalid Unsplash API key")
            return []
        except Exception as e:
            logger.error(f"Error searching Unsplash: {e}")
            return []
    
    def get_random_photo(self, query: str) -> Optional[UnsplashImage]:
        """
        Get a random photo matching the query.
        
        Args:
            query: Search terms
        
        Returns:
            UnsplashImage or None
        """
        url = f"{UNSPLASH_API_URL}/photos/random"
        params = {
            "query": query,
            "orientation": "landscape",
            "content_filter": "high",
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            photo = response.json()
            
            image = UnsplashImage(
                id=photo["id"],
                url=photo["urls"]["regular"],
                thumb_url=photo["urls"]["thumb"],
                download_url=photo["links"]["download_location"],
                photographer_name=photo["user"]["name"],
                photographer_url=photo["user"]["links"]["html"],
                unsplash_url=photo["links"]["html"],
                alt_text=photo.get("alt_description") or photo.get("description") or query,
            )
            
            logger.info(f"Got random image for query: {query}")
            return image
            
        except Exception as e:
            logger.error(f"Error getting random photo: {e}")
            return None
    
    def trigger_download(self, image: UnsplashImage) -> bool:
        """
        Trigger a download event for Unsplash tracking.
        Must be called when an image is used per Unsplash API guidelines.
        
        Args:
            image: The UnsplashImage being used
        
        Returns:
            True if successful
        """
        try:
            response = requests.get(image.download_url, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Triggered download for image: {image.id}")
            return True
        except Exception as e:
            logger.error(f"Error triggering download: {e}")
            return False
    
    def get_image_for_topic(self, topic: str, keywords: list[str] = None) -> Optional[UnsplashImage]:
        """
        Get the best image for a blog topic.
        
        Args:
            topic: The blog post topic/title
            keywords: Optional list of keywords to try
        
        Returns:
            UnsplashImage or None
        """
        # Build search queries from topic and keywords
        search_terms = [topic]
        if keywords:
            search_terms.extend(keywords[:3])  # Add up to 3 keywords
        
        # Try each search term until we find an image
        for term in search_terms:
            images = self.search_photos(term, per_page=3)
            if images:
                image = images[0]  # Take the first (most relevant) result
                # Trigger download tracking per Unsplash guidelines
                self.trigger_download(image)
                return image
        
        # Fallback: try generic tech terms
        fallback_terms = ["technology", "coding", "computer", "digital"]
        for term in fallback_terms:
            images = self.search_photos(term, per_page=1)
            if images:
                image = images[0]
                self.trigger_download(image)
                return image
        
        logger.warning(f"No image found for topic: {topic}")
        return None

