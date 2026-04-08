"""
Gemini AI client for generating blog topics and content.
Uses Google's Generative AI API with Gemini 3 Pro Preview model.
"""

import json
import re
import logging
from dataclasses import dataclass, field
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
    primary_keyword: str  # Main SEO keyword the post targets
    intro: str  # Introduction paragraph (HTML)
    key_takeaways: str  # TL;DR box HTML rendered after the intro
    sections: list[BlogSection]  # Main content sections
    conclusion: str  # Conclusion paragraph (HTML)
    cta_section: str  # Closing NohaTek CTA HTML (separate for styling)
    tags: list[str]
    image_keywords: list[str]  # Keywords for hero image
    video_keywords: list[str]  # Keywords for YouTube search

    @property
    def html_content(self) -> str:
        """Generate the full HTML content (without images/video - those are added later)."""
        parts = [self.intro]

        if self.key_takeaways:
            parts.append(self.key_takeaways)

        for section in self.sections:
            parts.append(f"<h2>{section.heading}</h2>")
            parts.append(section.content)

        parts.append(self.conclusion)

        if self.cta_section:
            parts.append(self.cta_section)

        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'slug': self.slug,
            'meta_description': self.meta_description,
            'primary_keyword': self.primary_keyword,
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

        # Configure model with longer timeout and higher token limit for deep blog generation
        generation_config = genai.GenerationConfig(
            temperature=0.75,
            max_output_tokens=16384,
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

            if in_string:
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                elif ord(char) < 32:
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
- Write directly about a trending topic if it fits NohaTek's expertise
- Find an angle that connects a trend to cloud/AI/DevOps/security/supply chain
- Analyze implications of a trend for retail, logistics, or supplier businesses
- Provide practical guidance related to trending news for the NWA business community"""

        prompt = f"""You are a senior SEO content strategist and tech editor for NohaTek, a technology consulting \
company based in Rogers, Arkansas in the heart of Northwest Arkansas (NWA). NohaTek is a technical partner for \
businesses in the NWA region, which is home to:
- Walmart (Bentonville) and its massive supplier/vendor ecosystem
- Tyson Foods (Springdale) and the food supply chain industry
- J.B. Hunt (Lowell) and the logistics/transportation sector
- Hundreds of CPG suppliers, tech companies, and startups serving these anchor enterprises

NohaTek specializes in:
- Cloud Infrastructure & DevOps
- AI & Machine Learning Services
- Software Development & API Integration
- Cybersecurity
- Supply Chain Technology & Logistics Solutions
- Retail Tech, EDI, & Supplier Integration
- Data Analytics & Business Intelligence
- Warehouse Automation & IoT

Your job is to identify the single BEST blog topic to publish today. The ideal topic must satisfy ALL of these criteria:

1. HIGH SEARCH DEMAND: People are actively Googling this topic right now. Think about what a CTO, IT manager, \
supply chain director, or developer would type into Google when they have a real problem to solve.

2. CONTENT GAP OPPORTUNITY: Favor topics where existing online content is thin, outdated (pre-2024), \
generic, or fails to address the NWA/supply chain/retail angle. We can outrank weak existing content.

3. BUYER INTENT: The topic should attract readers who are in the research phase of hiring a tech consultant \
or evaluating a technology solution — not just casual readers. Topics like "how to choose a cloud migration partner" \
or "EDI integration for Walmart suppliers" signal high purchase intent.

4. TITLE FORMAT: Use one of these proven high-performing formats:
   - "How to [achieve outcome] in [timeframe/context]"
   - "The [Year] Guide to [Topic]: [Specific Benefit]"
   - "[Number] Ways to [Solve Problem] with [Technology]"
   - "Why [Common Belief] Is Wrong (And What to Do Instead)"
   - "[Topic A] vs [Topic B]: Which Is Right for [Audience]?"
   - "The Hidden Costs of [Problem] — and How to Fix It"
   - "What [Audience] Gets Wrong About [Topic]"

5. LONG-TAIL SPECIFICITY: Avoid broad topics like "cloud computing" or "AI trends." Instead go specific: \
"How Walmart Suppliers Can Automate EDI Compliance with AI" or \
"Kubernetes Cost Optimization: 7 Fixes for Overspending DevOps Teams."

6. NWA / INDUSTRY RELEVANCE: Where possible, connect the topic to supply chain, retail, logistics, \
CPG manufacturing, or the NWA business community — this is our niche and differentiates us from generic tech blogs.

7. SEO TIMING: Prefer topics that are evergreen (will rank for years) OR currently spiking in search volume \
due to a recent industry development, regulation, or technology release.
{trending_str}

Our expertise areas: {', '.join(self.topics)}
{previous_str}

Respond with ONLY the topic title, nothing else. No quotes, no explanation. Make it a great headline."""

        try:
            response = self.model.generate_content(prompt)
            topic = response.text.strip().strip('"\'')
            logger.info(f"Generated topic: {topic}")
            return topic
        except Exception as e:
            logger.error(f"Error generating topic: {e}")
            raise

    def generate_blog_post(self, topic: str) -> 'BlogPost':
        """Generate a full blog post for the given topic with rich sections."""

        prompt = f"""You are an elite tech content writer and SEO specialist. Your mission is to write the \
DEFINITIVE blog post on this topic — one that ranks #1 on Google, keeps readers engaged start to finish, \
and converts readers into leads for NohaTek's consulting services.

TOPIC: "{topic}"

ABOUT NOHATEK:
NohaTek (nohatek.com) is a technology consulting company based in Rogers, Arkansas, serving as a strategic \
technical partner for businesses across Northwest Arkansas (NWA) and beyond. NWA is home to Walmart \
(Bentonville), Tyson Foods (Springdale), J.B. Hunt (Lowell), and hundreds of CPG suppliers, vendors, and \
tech startups that power global supply chains.

NohaTek's core services: Cloud Infrastructure & DevOps, AI & Machine Learning, Software Development & API \
Integration, Cybersecurity, Supply Chain Technology, Retail Tech & EDI, Data Analytics & Business Intelligence, \
Warehouse Automation & IoT.

TARGET AUDIENCE (write for ALL of these):
- CTOs, VPs of Technology, and IT directors making buy-or-build decisions
- Developers and DevOps engineers looking for best practices
- Supply chain managers and logistics directors evaluating tech solutions
- Retail and CPG technology teams (especially Walmart/Tyson/JBH supplier ecosystem)
- Business owners and operations leaders in NWA and beyond

═══════════════════════════════════════════════
SEO REQUIREMENTS (NON-NEGOTIABLE)
═══════════════════════════════════════════════

KEYWORD STRATEGY:
- Identify the single best PRIMARY KEYWORD for this topic (the exact phrase people Google)
- Weave in 4-6 SECONDARY KEYWORDS naturally throughout (related terms, synonyms, long-tail variants)
- Place the primary keyword in: title, first 100 words, at least 2 H2 headings, meta description, and slug
- Use LSI (latent semantic indexing) keywords — related concepts Google expects to see

TITLE (return in "title" field):
- 50-65 characters maximum
- Primary keyword front-loaded (within first 3 words if possible)
- Use a proven format: "How to...", "X Ways to...", "[Year] Guide...", "Why...", "vs.", or "The Truth About..."
- Must be compelling enough to earn a click even if ranking #3

META DESCRIPTION (return in "meta_description" field):
- Exactly 145-160 characters
- Contains primary keyword
- Written as a VALUE PROPOSITION, not a summary — tell the reader what they'll gain
- Include a soft call-to-action word (learn, discover, see how, find out)

SLUG (return in "slug" field):
- 3-6 words max, all lowercase, hyphen-separated
- Contains primary keyword

═══════════════════════════════════════════════
CONTENT QUALITY REQUIREMENTS (NON-NEGOTIABLE)
═══════════════════════════════════════════════

LENGTH: 1800-2500 words total across all sections. This is the sweet spot for ranking long-form content.

HOOK (first 2 sentences of intro MUST do one of these):
- Open with a surprising statistic or data point
- Ask a question that makes the reader feel seen ("If you're managing Walmart supplier compliance...")
- Make a bold, counterintuitive claim that challenges conventional wisdom
- Paint a vivid pain-point scenario the reader immediately recognizes

INTRO PARAGRAPH:
- 150-200 words
- Hook → establish the problem's stakes → preview what the post covers → why the reader should trust this source
- Do NOT start with "In today's digital world" or generic AI filler phrases
- End with a transition that pulls the reader into the body

KEY TAKEAWAYS BOX (return in "key_takeaways" field):
- Rendered as a styled HTML aside/callout immediately after the intro
- 4-6 bullet points summarizing the most valuable insights in the post
- Written for skimmers — someone who reads ONLY this box should still get value
- Use this HTML structure:
  <div class="kg-card kg-callout-card kg-callout-card-blue">
    <div class="kg-callout-emoji">💡</div>
    <div class="kg-callout-text"><strong>Key Takeaways</strong><ul><li>...</li></ul></div>
  </div>

BODY SECTIONS (4-6 sections):
Each section must:
- Have a clear H2 heading that contains a keyword or answers a specific question
- Be 300-450 words
- Include at least ONE of: a statistic with source, a real-world example, a case study scenario, or a concrete tool/technique
- Use H3 sub-headings to break up content within longer sections
- Have SHORT paragraphs (2-4 sentences max) — never a wall of text
- Use <ul> or <ol> lists for scannable content (at least one list per section)
- Use <strong> to bold the single most important phrase in each paragraph
- Use <blockquote> for key statistics, expert quotes, or insight callouts
- Use "bucket brigade" transition phrases between paragraphs to maintain momentum:
  ("Here's the thing:", "But there's a catch:", "The result?", "This is where it gets interesting:", etc.)
- At least ONE section should include a mini case-study or real-world scenario involving a company type \
  similar to NohaTek's clients (e.g., a Walmart supplier, a logistics company, a food manufacturer)

CONCLUSION (return in "conclusion" field):
- 150-200 words
- Summarize the 2-3 most important points
- Acknowledge the complexity and that every situation is different
- Transition naturally into the CTA section
- Do NOT end with "In conclusion,..." — that's lazy. Start with a forward-looking statement

CTA SECTION (return in "cta_section" field):
- Titled "How NohaTek Can Help" or "[Topic Area] Experts in Northwest Arkansas" (pick whichever fits better)
- 100-150 words
- Positions NohaTek as the natural next step — not a hard sell, but an obvious extension of the content
- Mention 1-2 specific NohaTek services that are directly relevant to the topic
- Include a hyperlink to nohatek.com: <a href="https://nohatek.com">nohatek.com</a>
- Include a hyperlink to contact: <a href="https://nohatek.com/contact">reach out to our team</a>
- Tone: confident and helpful, like a trusted advisor saying "here's where to go next"
- Wrap in: <div class="kg-card kg-callout-card kg-callout-card-grey">...</div>

═══════════════════════════════════════════════
WRITING STYLE STANDARDS
═══════════════════════════════════════════════

TONE: Expert but human. Write like the smartest person in the room who ALSO knows how to explain things clearly. \
Not academic, not salesy. Think: Harvard Business Review meets a knowledgeable colleague.

SENTENCES: Vary length deliberately. Mix punchy 6-word sentences with longer, more nuanced ones. \
This creates rhythm and keeps readers engaged.

VOICE: Active voice whenever possible. "NohaTek builds cloud solutions" not "Cloud solutions are built by NohaTek."

AVOID THESE PHRASES ENTIRELY (they signal AI-generated content and hurt credibility):
- "In today's fast-paced world"
- "In the digital age"
- "Leverage" (use "use" or "apply" instead)
- "Delve into"
- "It's worth noting that"
- "At the end of the day"
- "Game-changer" or "game-changing"
- "Cutting-edge" (unless quoting someone)
- "Unlock the potential"
- Any phrase starting with "In conclusion,"

NWA/INDUSTRY GROUNDING:
- Reference the NWA business ecosystem where it feels natural (at least once per post)
- Use specific, credible examples: "a Walmart supplier managing 50+ SKUs", "a J.B. Hunt fleet operator", etc.
- This grounds the content in NohaTek's actual expertise and differentiates from generic tech blogs

═══════════════════════════════════════════════
HTML FORMATTING FOR GHOST CMS
═══════════════════════════════════════════════

Use ONLY these HTML elements:
- <p> for paragraphs
- <h2> for section headings (these are handled separately — do NOT put <h2> inside section "content")
- <h3> for sub-headings within a section's content (encouraged for longer sections)
- <ul>/<li> and <ol>/<li> for lists
- <strong> for emphasis on key phrases
- <blockquote> for stats, quotes, and insight callouts
- <code> for inline code or technical terms
- <pre><code> for code blocks
- <a href="..."> for hyperlinks (use for nohatek.com links and any cited sources)
- Ghost callout cards (the div structures above) for key takeaways and CTA

Do NOT use: <h1>, <h4>-<h6>, <div> outside of the specified callout cards, inline styles, or <script>

═══════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════

Respond in this EXACT JSON format (no markdown code blocks, just raw JSON):
{{
    "primary_keyword": "the exact phrase people Google for this topic",
    "title": "SEO-optimized title (50-65 chars)",
    "slug": "primary-keyword-slug",
    "meta_description": "145-160 char value proposition with primary keyword and soft CTA",
    "intro": "<p>Hook sentence. Second hook/setup sentence.</p><p>Stakes paragraph...</p><p>What this post covers and why trust us...</p>",
    "key_takeaways": "<div class=\\"kg-card kg-callout-card kg-callout-card-blue\\"><div class=\\"kg-callout-emoji\\">💡</div><div class=\\"kg-callout-text\\"><strong>Key Takeaways</strong><ul><li>Insight 1</li><li>Insight 2</li><li>Insight 3</li><li>Insight 4</li><li>Insight 5</li></ul></div></div>",
    "sections": [
        {{
            "heading": "H2 Section Title with Keyword",
            "content": "<p>Paragraph with <strong>key phrase bolded</strong>.</p><h3>Sub-section Title</h3><p>More content...</p><ul><li>Point 1</li><li>Point 2</li></ul><blockquote>Key stat or insight.</blockquote>",
            "image_keyword": "specific visual search term for Unsplash"
        }},
        {{
            "heading": "Second Section Title",
            "content": "<p>Content...</p>",
            "image_keyword": "visual keyword"
        }},
        {{
            "heading": "Third Section Title",
            "content": "<p>Content...</p>",
            "image_keyword": "visual keyword"
        }},
        {{
            "heading": "Fourth Section Title",
            "content": "<p>Content...</p>",
            "image_keyword": "visual keyword"
        }}
    ],
    "conclusion": "<p>Forward-looking opening sentence. Key takeaways summary...</p><p>Transition to next steps...</p>",
    "cta_section": "<div class=\\"kg-card kg-callout-card kg-callout-card-grey\\"><div class=\\"kg-callout-text\\"><h2>How NohaTek Can Help</h2><p>CTA content with <a href=\\"https://nohatek.com\\">nohatek.com</a> link and <a href=\\"https://nohatek.com/contact\\">reach out to our team</a> link.</p></div></div>",
    "tags": ["PrimaryTag", "Tag2", "Tag3", "Tag4", "Tag5"],
    "image_keywords": ["hero image keyword", "secondary keyword", "tertiary keyword"],
    "video_keywords": ["specific youtube tutorial search", "explainer search term"]
}}

IMPORTANT: Write the FULL post. Do not truncate, summarize, or use placeholder text. \
Every field must contain complete, publish-ready content. This post should be so good that \
a reader bookmarks it, shares it, and remembers NohaTek as the source."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group()

            response_text = self._clean_json_response(response_text)

            data = json.loads(response_text)

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
                primary_keyword=data.get('primary_keyword', topic),
                intro=data.get('intro', '<p></p>'),
                key_takeaways=data.get('key_takeaways', ''),
                sections=sections,
                conclusion=data.get('conclusion', '<p></p>'),
                cta_section=data.get('cta_section', ''),
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

    def regenerate_with_feedback(self, topic: str, feedback: str) -> 'BlogPost':
        """Regenerate a blog post with specific feedback/modifications."""

        prompt = f"""You are an elite tech content writer and SEO specialist. Rewrite the blog post on \
"{topic}" incorporating the following feedback:

FEEDBACK TO INCORPORATE: {feedback}

Apply all feedback precisely while maintaining the highest content quality standards below.

ABOUT NOHATEK:
NohaTek (nohatek.com) is a technology consulting company based in Rogers, Arkansas, serving businesses \
across Northwest Arkansas (NWA) — home to Walmart (Bentonville), Tyson Foods (Springdale), J.B. Hunt \
(Lowell), and hundreds of CPG suppliers and tech startups.

NohaTek's services: Cloud Infrastructure & DevOps, AI & Machine Learning, Software Development & API \
Integration, Cybersecurity, Supply Chain Technology, Retail Tech & EDI, Data Analytics, Warehouse Automation.

TARGET AUDIENCE: CTOs, IT directors, developers, DevOps engineers, supply chain managers, retail/CPG tech \
teams, and business leaders in NWA and beyond.

CONTENT STANDARDS:
- Length: 1800-2500 words across 4-6 sections
- Hook: open with a stat, bold claim, or relatable pain-point scenario — NO generic AI phrases
- Every section: data points or real-world examples, short paragraphs (2-4 sentences), lists, bolded key phrases
- SEO: primary keyword in title, first 100 words, 2+ H2s, meta description, and slug
- Tone: expert but human — like a trusted advisor, not a salesperson
- NWA grounding: reference the NWA ecosystem or supply chain/retail industry at least once
- Include a Key Takeaways callout box after the intro (4-6 bullets for skimmers)
- Include a closing CTA section linking to nohatek.com and nohatek.com/contact

BANNED PHRASES: "In today's fast-paced world", "leverage", "delve into", "game-changer", "cutting-edge", \
"unlock the potential", "In conclusion,", "In the digital age", "it's worth noting"

HTML RULES: Use <p>, <h3> (inside sections), <ul>/<li>, <ol>/<li>, <strong>, <blockquote>, <code>, \
<pre><code>, <a href>. Ghost callout cards for key takeaways and CTA sections.

Respond in this EXACT JSON format (no markdown code blocks, just raw JSON):
{{
    "primary_keyword": "the exact phrase people Google for this topic",
    "title": "SEO-optimized title (50-65 chars, primary keyword front-loaded)",
    "slug": "primary-keyword-slug",
    "meta_description": "145-160 char value proposition with primary keyword and soft CTA",
    "intro": "<p>Hook. Setup.</p><p>Stakes and preview...</p>",
    "key_takeaways": "<div class=\\"kg-card kg-callout-card kg-callout-card-blue\\"><div class=\\"kg-callout-emoji\\">💡</div><div class=\\"kg-callout-text\\"><strong>Key Takeaways</strong><ul><li>Insight 1</li><li>Insight 2</li><li>Insight 3</li><li>Insight 4</li></ul></div></div>",
    "sections": [
        {{"heading": "Section Title", "content": "<p>Full content...</p>", "image_keyword": "visual keyword"}}
    ],
    "conclusion": "<p>Forward-looking opening. Summary of key points. Transition to CTA...</p>",
    "cta_section": "<div class=\\"kg-card kg-callout-card kg-callout-card-grey\\"><div class=\\"kg-callout-text\\"><h2>How NohaTek Can Help</h2><p>CTA with <a href=\\"https://nohatek.com\\">nohatek.com</a> and <a href=\\"https://nohatek.com/contact\\">reach out to our team</a>.</p></div></div>",
    "tags": ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"],
    "image_keywords": ["hero keyword", "keyword2", "keyword3"],
    "video_keywords": ["youtube search term"]
}}

Write the FULL post — no placeholders, no truncation. Publish-ready content only."""

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                response_text = json_match.group()

            response_text = self._clean_json_response(response_text)

            data = json.loads(response_text)

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
                primary_keyword=data.get('primary_keyword', topic),
                intro=data.get('intro', '<p></p>'),
                key_takeaways=data.get('key_takeaways', ''),
                sections=sections,
                conclusion=data.get('conclusion', '<p></p>'),
                cta_section=data.get('cta_section', ''),
                tags=data['tags'][:5],
                image_keywords=data.get('image_keywords', [topic])[:3],
                video_keywords=data.get('video_keywords', [topic])[:2],
            )
        except Exception as e:
            logger.error(f"Error regenerating blog post: {e}")
            raise
