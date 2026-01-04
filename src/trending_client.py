"""
Trending topics client that fetches real-time tech news from free sources.
Uses Hacker News API and tech RSS feeds to provide current trending topics.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

import requests
import feedparser

logger = logging.getLogger(__name__)


@dataclass
class TrendingTopic:
    """Represents a trending topic from an external source."""
    title: str
    source: str
    url: Optional[str] = None
    score: Optional[int] = None  # For HN stories


class TrendingClient:
    """Fetches trending tech topics from multiple free sources."""
    
    # Hacker News API endpoints
    HN_TOP_STORIES = "https://hacker-news.firebaseio.com/v0/topstories.json"
    HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{}.json"
    
    # Tech RSS feeds (no API key required)
    RSS_FEEDS = [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Wired", "https://www.wired.com/feed/rss"),
    ]
    
    # Cache settings
    CACHE_TTL_SECONDS = 3600  # 1 hour
    
    def __init__(self):
        self._cache: list[TrendingTopic] = []
        self._cache_time: float = 0
        self._executor = ThreadPoolExecutor(max_workers=5)
    
    def get_trending_topics(self, limit: int = 20) -> list[str]:
        """
        Get a list of trending topic titles.
        
        Args:
            limit: Maximum number of topics to return
            
        Returns:
            List of trending topic titles as strings
        """
        topics = self._get_cached_or_fetch()
        
        # Return just the titles, deduplicated
        seen = set()
        unique_titles = []
        for topic in topics:
            # Normalize title for deduplication
            normalized = topic.title.lower().strip()
            if normalized not in seen and len(topic.title) > 10:
                seen.add(normalized)
                unique_titles.append(topic.title)
                if len(unique_titles) >= limit:
                    break
        
        return unique_titles
    
    def _get_cached_or_fetch(self) -> list[TrendingTopic]:
        """Return cached topics or fetch fresh ones."""
        now = time.time()
        
        if self._cache and (now - self._cache_time) < self.CACHE_TTL_SECONDS:
            logger.debug("Using cached trending topics")
            return self._cache
        
        logger.info("Fetching fresh trending topics...")
        topics = self._fetch_all_topics()
        
        if topics:
            self._cache = topics
            self._cache_time = now
            logger.info(f"Cached {len(topics)} trending topics")
        
        return topics
    
    def _fetch_all_topics(self) -> list[TrendingTopic]:
        """Fetch topics from all sources."""
        all_topics = []
        
        # Fetch from Hacker News
        try:
            hn_topics = self._fetch_hacker_news(limit=15)
            all_topics.extend(hn_topics)
            logger.info(f"Fetched {len(hn_topics)} topics from Hacker News")
        except Exception as e:
            logger.warning(f"Failed to fetch from Hacker News: {e}")
        
        # Fetch from RSS feeds
        for feed_name, feed_url in self.RSS_FEEDS:
            try:
                rss_topics = self._fetch_rss_feed(feed_name, feed_url, limit=5)
                all_topics.extend(rss_topics)
                logger.debug(f"Fetched {len(rss_topics)} topics from {feed_name}")
            except Exception as e:
                logger.warning(f"Failed to fetch from {feed_name}: {e}")
        
        # Sort by score (HN stories) then by source diversity
        all_topics.sort(key=lambda t: (t.score or 0), reverse=True)
        
        return all_topics
    
    def _fetch_hacker_news(self, limit: int = 15) -> list[TrendingTopic]:
        """Fetch top stories from Hacker News."""
        topics = []
        
        # Get top story IDs
        response = requests.get(self.HN_TOP_STORIES, timeout=10)
        response.raise_for_status()
        story_ids = response.json()[:limit * 2]  # Fetch extra in case some fail
        
        # Fetch story details (in parallel for speed)
        def fetch_story(story_id):
            try:
                resp = requests.get(self.HN_ITEM.format(story_id), timeout=5)
                resp.raise_for_status()
                return resp.json()
            except Exception:
                return None
        
        # Use thread pool for parallel fetching
        stories = list(self._executor.map(fetch_story, story_ids))
        
        for story in stories:
            if story and story.get('title'):
                # Filter out job postings, Ask HN, etc. for cleaner topics
                title = story['title']
                if not any(prefix in title for prefix in ['Ask HN:', 'Tell HN:', 'Show HN:', 'Hiring:']):
                    topics.append(TrendingTopic(
                        title=title,
                        source="Hacker News",
                        url=story.get('url'),
                        score=story.get('score', 0),
                    ))
                    if len(topics) >= limit:
                        break
        
        return topics
    
    def _fetch_rss_feed(self, feed_name: str, feed_url: str, limit: int = 5) -> list[TrendingTopic]:
        """Fetch topics from an RSS feed."""
        topics = []
        
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries[:limit]:
            title = entry.get('title', '').strip()
            if title:
                topics.append(TrendingTopic(
                    title=title,
                    source=feed_name,
                    url=entry.get('link'),
                ))
        
        return topics
    
    def get_topics_summary(self) -> str:
        """
        Get a formatted summary of trending topics for the AI prompt.
        
        Returns:
            A string summary of current trending topics
        """
        topics = self._get_cached_or_fetch()
        
        if not topics:
            return ""
        
        # Group by source
        by_source = {}
        for topic in topics:
            if topic.source not in by_source:
                by_source[topic.source] = []
            by_source[topic.source].append(topic.title)
        
        # Build summary
        lines = ["Current trending tech topics:"]
        for source, titles in by_source.items():
            lines.append(f"\n{source}:")
            for title in titles[:5]:  # Max 5 per source
                lines.append(f"  - {title}")
        
        return "\n".join(lines)
