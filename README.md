# Ghost Auto Blog Generator

Automated blog post generator that uses **Gemini AI** to create tech content and publishes to your **Ghost CMS** blog. Features a **Telegram bot** for reviewing and approving posts before publishing.

## Features

- 🤖 **AI-Powered Content** - Uses Gemini 3 Pro Preview to generate high-quality tech blog posts
- 📱 **Telegram Approval** - Review drafts via Telegram before publishing
- ⏰ **Scheduled Generation** - Automatically generates posts on a configurable schedule
- 🏷️ **Auto-Tagging** - AI generates relevant tags for SEO
- 🐳 **Docker Ready** - Easy deployment via Docker/Coolify

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ghostai.git
cd ghostai
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```env
# Ghost CMS Configuration
GHOST_ADMIN_API_KEY=your_key_id:your_secret
GHOST_URL=https://your-ghost-blog.com

# Gemini AI Configuration
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3-pro-preview

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_USER_ID=your_numeric_telegram_id

# Schedule (optional, default: 24 hours)
POST_SCHEDULE_HOURS=24
```

### 3. Get Your Credentials

**Ghost Admin API Key:**
1. Go to Ghost Admin → Settings → Integrations
2. Click "Add custom integration"
3. Copy the Admin API key (format: `id:secret`)

**Gemini API Key:**
1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Create a new API key

**Telegram Bot Token:**
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the token it gives you

**Telegram User ID:**
1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your numeric ID

### 4. Run with Docker (Recommended)

```bash
docker compose up -d
```

Or build and run manually:

```bash
docker build -t ghost-auto-blog .
docker run -d --env-file .env ghost-auto-blog
```

### 5. Run Locally (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the bot
python -m src.main
```

## Telegram Commands

Once running, message your bot on Telegram:

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message |
| `/generate` | Manually create a new blog post |
| `/status` | Check bot and API connection status |
| `/topics` | Generate 5 topic ideas |
| `/help` | Show help message |

## Approval Workflow

1. Bot generates a new post (scheduled or via `/generate`)
2. You receive a draft preview on Telegram
3. Choose an action:
   - ✅ **Approve** - Publishes to Ghost immediately
   - ❌ **Reject** - Discards the draft
   - 🔄 **Regenerate** - Creates a new version

## Deployment on Coolify

1. Connect your GitHub repository to Coolify
2. Select "Docker Compose" as the build method
3. Add environment variables in Coolify's settings:
   - `GHOST_ADMIN_API_KEY`
   - `GHOST_URL`
   - `GEMINI_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_USER_ID`
   - `POST_SCHEDULE_HOURS` (optional)
4. Deploy!

## Project Structure

```
ghostai/
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point & scheduler
│   ├── config.py            # Configuration management
│   ├── gemini_client.py     # Gemini AI integration
│   ├── ghost_client.py      # Ghost Admin API client
│   └── telegram_bot.py      # Telegram bot & approval flow
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GHOST_ADMIN_API_KEY` | Yes | - | Ghost Admin API key |
| `GHOST_URL` | Yes | - | Your Ghost blog URL |
| `GEMINI_API_KEY` | Yes | - | Google Gemini API key |
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram bot token |
| `TELEGRAM_USER_ID` | Yes | - | Your Telegram user ID |
| `GEMINI_MODEL` | No | `gemini-3-pro-preview` | Gemini model to use |
| `POST_SCHEDULE_HOURS` | No | `24` | Hours between auto-posts |

## Content Focus

The bot generates content focused on:
- Cloud Infrastructure & DevOps
- AI & Machine Learning
- Software Development
- Cybersecurity
- Kubernetes, Docker, CI/CD
- API Development
- Infrastructure as Code

## License

MIT License - feel free to use and modify for your own projects.

## Support

For issues and questions, please open a GitHub issue.
