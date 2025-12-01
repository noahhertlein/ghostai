"""
Ghost CMS client for publishing blog posts via Admin API.
Uses JWT authentication as required by Ghost Admin API.
"""

import logging
from datetime import datetime
from typing import Optional

import jwt
import requests

from .config import get_config
from .gemini_client import BlogPost

logger = logging.getLogger(__name__)


class GhostClient:
    """Client for interacting with Ghost Admin API."""
    
    def __init__(self):
        config = get_config()
        self.api_key = config.ghost_admin_api_key
        self.base_url = config.ghost_url
        
        # Split the key into ID and SECRET
        try:
            self.key_id, self.key_secret = self.api_key.split(':')
        except ValueError:
            raise ValueError("Invalid Ghost Admin API key format. Expected 'id:secret'")
    
    def _generate_token(self) -> str:
        """Generate a JWT token for Ghost Admin API authentication."""
        iat = int(datetime.now().timestamp())
        
        header = {
            'alg': 'HS256',
            'typ': 'JWT',
            'kid': self.key_id
        }
        
        payload = {
            'iat': iat,
            'exp': iat + 5 * 60,  # Token expires in 5 minutes
            'aud': '/admin/'
        }
        
        token = jwt.encode(
            payload,
            bytes.fromhex(self.key_secret),
            algorithm='HS256',
            headers=header
        )
        
        return token
    
    def _get_headers(self) -> dict:
        """Get authentication headers for API requests."""
        token = self._generate_token()
        return {
            'Authorization': f'Ghost {token}',
            'Content-Type': 'application/json'
        }
    
    def publish_post(self, blog_post: BlogPost, status: str = 'published') -> dict:
        """
        Publish a blog post to Ghost.
        
        Args:
            blog_post: The BlogPost object to publish
            status: 'published' or 'draft'
        
        Returns:
            The created post data from Ghost API
        """
        url = f"{self.base_url}/ghost/api/admin/posts/?source=html"
        
        # Build tags array
        tags = [{'name': tag} for tag in blog_post.tags]
        
        # Build the post payload
        payload = {
            'posts': [{
                'title': blog_post.title,
                'slug': blog_post.slug,
                'html': blog_post.html_content,
                'status': status,
                'meta_description': blog_post.meta_description,
                'tags': tags,
                'custom_excerpt': blog_post.meta_description,
            }]
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            post_data = response.json()['posts'][0]
            logger.info(f"Published post: {post_data['title']} (ID: {post_data['id']})")
            return post_data
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error publishing post: {e}")
            logger.error(f"Response: {e.response.text if e.response else 'No response'}")
            raise
        except Exception as e:
            logger.error(f"Error publishing post: {e}")
            raise
    
    def update_post(self, post_id: str, updates: dict) -> dict:
        """
        Update an existing post.
        
        Args:
            post_id: The Ghost post ID
            updates: Dictionary of fields to update
        
        Returns:
            The updated post data
        """
        # First, get the current post to get updated_at
        get_url = f"{self.base_url}/ghost/api/admin/posts/{post_id}"
        
        try:
            response = requests.get(get_url, headers=self._get_headers())
            response.raise_for_status()
            current_post = response.json()['posts'][0]
            
            # Now update the post
            update_url = f"{self.base_url}/ghost/api/admin/posts/{post_id}/?source=html"
            
            payload = {
                'posts': [{
                    **updates,
                    'updated_at': current_post['updated_at']
                }]
            }
            
            response = requests.put(
                update_url,
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            post_data = response.json()['posts'][0]
            logger.info(f"Updated post: {post_data['title']} (ID: {post_data['id']})")
            return post_data
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error updating post: {e}")
            raise
        except Exception as e:
            logger.error(f"Error updating post: {e}")
            raise
    
    def delete_post(self, post_id: str) -> bool:
        """
        Delete a post by ID.
        
        Args:
            post_id: The Ghost post ID
        
        Returns:
            True if successful
        """
        url = f"{self.base_url}/ghost/api/admin/posts/{post_id}"
        
        try:
            response = requests.delete(url, headers=self._get_headers())
            response.raise_for_status()
            logger.info(f"Deleted post ID: {post_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting post: {e}")
            raise
    
    def get_posts(self, limit: int = 15) -> list:
        """
        Get recent posts from Ghost.
        
        Args:
            limit: Number of posts to retrieve
        
        Returns:
            List of post objects
        """
        url = f"{self.base_url}/ghost/api/admin/posts/?limit={limit}"
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()['posts']
        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            raise
    
    def get_recent_titles(self, limit: int = 20) -> list[str]:
        """Get titles of recent posts to avoid duplicate topics."""
        posts = self.get_posts(limit=limit)
        return [post['title'] for post in posts]
    
    def test_connection(self) -> bool:
        """Test the connection to Ghost API."""
        try:
            posts = self.get_posts(limit=1)
            logger.info("Ghost API connection successful")
            return True
        except Exception as e:
            logger.error(f"Ghost API connection failed: {e}")
            return False

