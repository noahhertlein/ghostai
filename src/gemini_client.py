"""
Gemini AI client for generating blog topics and content.
Uses Google's Generative AI API with Gemini 3 Pro Preview model.
"""

import json
import re
import logging
from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai

from .config import get_config

logger = logging.getLogger(__name__)


@dataclass
class BlogPost:
    """Represents a generated blog post."""
    title: str
    slug: str
    meta_description: str
    html_content: str
    tags: list[str]
    image_keywords: list[str]  # Keywords for Unsplash image search
    
    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'slug': self.slug,
            'meta_description': self.meta_description,
            'html_content': self.html_content,
            'tags': self.tags,
            'image_keywords': self.image_keywords,
        }


class GeminiClient:
    """Client for interacting with Gemini AI API."""
    
    def __init__(self):
        config = get_config()
        genai.configure(api_key=config.gemini_api_key)
        self.model = genai.GenerativeModel(config.gemini_model)
        self.topics = config.topics
    
    def generate_topic(self, previous_topics: list[str] = None) -> str:
        """Generate a fresh blog topic idea."""
        
        previous_str = ""
        if previous_topics:
            previous_str = f"\n\nAvoid these recently covered topics:\n" + "\n".join(f"- {t}" for t in previous_topics[-20:])
        
        prompt = f"""You are a tech content strategist for Nohatek, a company specializing in:
- Cloud Infrastructure & DevOps
- AI & Machine Learning Services
- Software Development
- Cybersecurity

Generate ONE specific, engaging blog topic idea that would interest potential customers and tech professionals.

The topic should be:
1. Timely and relevant to current tech trends
2. Specific enough to write a focused article (not too broad)
3. Actionable or educational for the reader
4. SEO-friendly with good search potential

Focus areas to choose from: {', '.join(self.topics)}
{previous_str}

Respond with ONLY the topic title, nothing else. No quotes, no explanation."""

        try:
            response = self.model.generate_content(prompt)
            topic = response.text.strip().strip('"\'')
            logger.info(f"Generated topic: {topic}")
            return topic
        except Exception as e:
            logger.error(f"Error generating topic: {e}")
            raise
    
    def generate_blog_post(self, topic: str) -> BlogPost:
        """Generate a full blog post for the given topic."""
        
        prompt = f"""Write a professional, engaging blog post about: "{topic}"

This is for Nohatek's tech blog (intel.nohatek.com), targeting:
- IT professionals and developers
- CTOs and tech decision makers
- Companies looking for cloud, AI, or development services

Requirements:
1. Write in a professional but approachable tone
2. Include practical insights, examples, or actionable advice
3. Use proper HTML formatting for Ghost CMS
4. Length: 800-1200 words
5. Make it SEO-optimized

Respond in this exact JSON format (no markdown code blocks, just raw JSON):
{{
    "title": "Engaging SEO-friendly title",
    "slug": "url-friendly-slug-with-dashes",
    "meta_description": "Compelling 150-160 character description for search results",
    "html_content": "<p>Full HTML content here...</p>",
    "tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"],
    "image_keywords": ["keyword1", "keyword2", "keyword3"]
}}

For html_content:
- Use <h2> for main sections, <h3> for subsections
- Use <p> for paragraphs
- Use <ul>/<li> or <ol>/<li> for lists
- Use <strong> for emphasis
- Use <blockquote> for important quotes or callouts
- Use <code> for inline code mentions
- Use <pre><code> for code blocks
- Do NOT include <h1> (Ghost adds the title automatically)
- Do NOT include any scripts or external resources

Tags should be single words or short phrases, capitalized properly.

image_keywords should be 3 simple, visual search terms for finding a relevant header image (e.g., "cloud computing", "server room", "cybersecurity")."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group()
            
            data = json.loads(response_text)
            
            blog_post = BlogPost(
                title=data['title'],
                slug=data['slug'].lower().replace(' ', '-'),
                meta_description=data['meta_description'],
                html_content=data['html_content'],
                tags=data['tags'][:5],  # Limit to 5 tags
                image_keywords=data.get('image_keywords', [topic])[:3],  # Fallback to topic
            )
            
            logger.info(f"Generated blog post: {blog_post.title}")
            return blog_post
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON: {e}")
            logger.error(f"Response was: {response_text[:500]}...")
            raise ValueError(f"Failed to parse blog post response: {e}")
        except KeyError as e:
            logger.error(f"Missing required field in response: {e}")
            raise ValueError(f"Missing required field in blog post: {e}")
        except Exception as e:
            logger.error(f"Error generating blog post: {e}")
            raise
    
    def regenerate_with_feedback(self, topic: str, feedback: str) -> BlogPost:
        """Regenerate a blog post with specific feedback/modifications."""
        
        prompt = f"""Write a professional blog post about: "{topic}"

Previous feedback to incorporate: {feedback}

This is for Nohatek's tech blog (intel.nohatek.com), targeting IT professionals, developers, and tech decision makers.

Respond in this exact JSON format (no markdown code blocks, just raw JSON):
{{
    "title": "Engaging SEO-friendly title",
    "slug": "url-friendly-slug-with-dashes",
    "meta_description": "Compelling 150-160 character description for search results",
    "html_content": "<p>Full HTML content here...</p>",
    "tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"],
    "image_keywords": ["keyword1", "keyword2", "keyword3"]
}}

Use proper HTML formatting. Length: 800-1200 words.
image_keywords should be 3 simple visual search terms for finding a header image."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group()
            
            data = json.loads(response_text)
            
            return BlogPost(
                title=data['title'],
                slug=data['slug'].lower().replace(' ', '-'),
                meta_description=data['meta_description'],
                html_content=data['html_content'],
                tags=data['tags'][:5],
                image_keywords=data.get('image_keywords', [topic])[:3],
            )
        except Exception as e:
            logger.error(f"Error regenerating blog post: {e}")
            raise

