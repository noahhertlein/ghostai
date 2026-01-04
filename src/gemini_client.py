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
class BlogSection:
    """Represents a section of a blog post."""
    heading: str
    content: str  # HTML content for this section
    image_keyword: str  # Keyword for finding an image for this section


@dataclass
class BlogPost:
    """Represents a generated blog post."""
    title: str
    slug: str
    meta_description: str
    intro: str  # Introduction paragraph (HTML)
    sections: list[BlogSection]  # Main content sections
    conclusion: str  # Conclusion paragraph (HTML)
    tags: list[str]
    image_keywords: list[str]  # Keywords for hero image
    video_keywords: list[str]  # Keywords for YouTube search
    
    @property
    def html_content(self) -> str:
        """Generate the full HTML content (without images/video - those are added later)."""
        parts = [self.intro]
        for section in self.sections:
            parts.append(f"<h2>{section.heading}</h2>")
            parts.append(section.content)
        parts.append(self.conclusion)
        return "\n".join(parts)
    
    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'slug': self.slug,
            'meta_description': self.meta_description,
            'html_content': self.html_content,
            'tags': self.tags,
            'image_keywords': self.image_keywords,
            'video_keywords': self.video_keywords,
        }


class GeminiClient:
    """Client for interacting with Gemini AI API."""
    
    def __init__(self):
        config = get_config()
        genai.configure(api_key=config.gemini_api_key)
        
        # Configure model with longer timeout for blog generation
        generation_config = genai.GenerationConfig(
            temperature=0.7,
            max_output_tokens=8192,
        )
        self.model = genai.GenerativeModel(
            config.gemini_model,
            generation_config=generation_config
        )
        self.topics = config.topics
    
    def _clean_json_response(self, text: str) -> str:
        """
        Clean up JSON response from Gemini to handle control characters.
        Gemini sometimes includes unescaped newlines/tabs in JSON strings.
        """
        # Track if we're inside a JSON string
        result = []
        in_string = False
        escape_next = False
        
        for char in text:
            if escape_next:
                result.append(char)
                escape_next = False
                continue
            
            if char == '\\':
                result.append(char)
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                result.append(char)
                continue
            
            # If inside a string, escape control characters
            if in_string:
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                elif ord(char) < 32:  # Other control characters
                    result.append(f'\\u{ord(char):04x}')
                else:
                    result.append(char)
            else:
                result.append(char)
        
        return ''.join(result)
    
    def generate_topic(self, previous_topics: list[str] = None, trending_topics: list[str] = None) -> str:
        """Generate a fresh blog topic idea, optionally informed by trending topics."""
        
        previous_str = ""
        if previous_topics:
            previous_str = f"\n\nAvoid these recently covered topics:\n" + "\n".join(f"- {t}" for t in previous_topics[-20:])
        
        trending_str = ""
        if trending_topics:
            trending_str = f"""

CURRENT TRENDING TOPICS IN TECH (use these as inspiration for timely content):
{chr(10).join(f'- {t}' for t in trending_topics[:15])}

Use these trends as inspiration to write about something timely and newsworthy. You can:
- Write directly about a trending topic if it fits Nohatek's expertise
- Find an angle that connects a trend to cloud/AI/DevOps/security
- Analyze implications of a trend for businesses
- Provide practical guidance related to trending news"""
        
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
{trending_str}

Our expertise areas: {', '.join(self.topics)}
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
        """Generate a full blog post for the given topic with rich sections."""
        
        prompt = f"""Write a professional, engaging blog post about: "{topic}"

This is for Nohatek's tech blog (intel.nohatek.com), targeting:
- IT professionals and developers
- CTOs and tech decision makers
- Companies looking for cloud, AI, or development services

Requirements:
1. Write in a professional but approachable tone
2. Include practical insights, examples, or actionable advice
3. Use proper HTML formatting for Ghost CMS
4. Length: 1000-1500 words total
5. Make it SEO-optimized
6. Structure with clear sections (3-4 main sections)

Respond in this exact JSON format (no markdown code blocks, just raw JSON):
{{
    "title": "Engaging SEO-friendly title",
    "slug": "url-friendly-slug-with-dashes",
    "meta_description": "Compelling 150-160 character description for search results",
    "intro": "<p>Engaging introduction paragraph that hooks the reader...</p>",
    "sections": [
        {{
            "heading": "First Section Title",
            "content": "<p>Section content with multiple paragraphs...</p>",
            "image_keyword": "relevant visual keyword"
        }},
        {{
            "heading": "Second Section Title", 
            "content": "<p>Section content...</p>",
            "image_keyword": "relevant visual keyword"
        }},
        {{
            "heading": "Third Section Title",
            "content": "<p>Section content...</p>",
            "image_keyword": "relevant visual keyword"
        }}
    ],
    "conclusion": "<p>Strong conclusion with call-to-action...</p>",
    "tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"],
    "image_keywords": ["hero image keyword1", "keyword2", "keyword3"],
    "video_keywords": ["youtube search term1", "search term2"]
}}

For HTML content in intro, sections, and conclusion:
- Use <p> for paragraphs
- Use <ul>/<li> or <ol>/<li> for lists
- Use <strong> for emphasis
- Use <blockquote> for important quotes or callouts
- Use <code> for inline code mentions
- Use <pre><code> for code blocks
- Do NOT use <h2> in section content (headings are separate)
- Do NOT include any scripts or external resources

Each section's image_keyword should be a simple visual search term for Unsplash.
video_keywords should be terms to find a relevant YouTube tutorial/explainer."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group()
            
            # Clean up control characters that break JSON parsing
            response_text = self._clean_json_response(response_text)
            
            data = json.loads(response_text)
            
            # Parse sections
            sections = []
            for section_data in data.get('sections', []):
                section = BlogSection(
                    heading=section_data['heading'],
                    content=section_data['content'],
                    image_keyword=section_data.get('image_keyword', topic),
                )
                sections.append(section)
            
            blog_post = BlogPost(
                title=data['title'],
                slug=data['slug'].lower().replace(' ', '-'),
                meta_description=data['meta_description'],
                intro=data.get('intro', '<p></p>'),
                sections=sections,
                conclusion=data.get('conclusion', '<p></p>'),
                tags=data['tags'][:5],
                image_keywords=data.get('image_keywords', [topic])[:3],
                video_keywords=data.get('video_keywords', [topic])[:2],
            )
            
            logger.info(f"Generated blog post: {blog_post.title} with {len(sections)} sections")
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
    "intro": "<p>Engaging introduction...</p>",
    "sections": [
        {{"heading": "Section Title", "content": "<p>Content...</p>", "image_keyword": "keyword"}}
    ],
    "conclusion": "<p>Conclusion...</p>",
    "tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"],
    "image_keywords": ["keyword1", "keyword2", "keyword3"],
    "video_keywords": ["youtube search term"]
}}

Use proper HTML formatting. Length: 1000-1500 words with 3-4 sections."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group()
            
            # Clean up control characters
            response_text = self._clean_json_response(response_text)
            
            data = json.loads(response_text)
            
            # Parse sections
            sections = []
            for section_data in data.get('sections', []):
                section = BlogSection(
                    heading=section_data['heading'],
                    content=section_data['content'],
                    image_keyword=section_data.get('image_keyword', topic),
                )
                sections.append(section)
            
            return BlogPost(
                title=data['title'],
                slug=data['slug'].lower().replace(' ', '-'),
                meta_description=data['meta_description'],
                intro=data.get('intro', '<p></p>'),
                sections=sections,
                conclusion=data.get('conclusion', '<p></p>'),
                tags=data['tags'][:5],
                image_keywords=data.get('image_keywords', [topic])[:3],
                video_keywords=data.get('video_keywords', [topic])[:2],
            )
        except Exception as e:
            logger.error(f"Error regenerating blog post: {e}")
            raise

