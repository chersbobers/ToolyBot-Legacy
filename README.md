# Tooly Bot

![Tooly Bot](https://files.catbox.moe/6fi55l.png)

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org)
[![Discord.py](https://img.shields.io/badge/discord.py-2.0%2B-blue)](https://discordpy.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Free](https://img.shields.io/badge/Free-100%25-success)](https://github.com/chersbobers/ToolyBot)
[![Open Source](https://img.shields.io/badge/Open%20Source-%E2%9D%A4-red)](https://github.com/chersbobers/ToolyBot)
[![Gif]](https://camo.githubusercontent.com/b1dcbf1c23a05137ae7c7fdf544082550382791048ee360022c288b87f022d6d/68747470733a2f2f692e67697068792e636f6d2f6d656469612f4c4d7439363338644f38646674416a74636f2f3230302e77656270)(100px,100px)
A completely free and open source Discord bot with leveling, economy, fishing, moderation, and more. Self-host it, customize it, make it yours.

## Features

- **Leveling** - XP from chat activity
- **Economy** - Daily rewards, work, wallet/bank
- **Fishing** - 18 fish types with rarities
- **Shop** - Custom roles, badges, items
- **Gambling** - Coin betting system
- **Moderation** - Auto content filtering
- **YouTube Notifications** - Video alerts
- **Fun Commands** - Jokes, pets, 8ball, dice
- **Search** - Images (Pexels) and music

## Quick Setup

### 1. Install Dependencies

```bash
git clone https://github.com/chersbobers/ToolyBot.git
cd ToolyBot
pip install discord.py aiohttp feedparser duckduckgo-search beautifulsoup4 psutil
```

### 2. Configure Environment

Create `.env` file:

```env
TOKEN=your_discord_bot_token
PORT=3000
```

Optional variables:

```env
YOUTUBE_CHANNEL_ID=UCxxxxxxxxx
NOTIFICATION_CHANNEL_ID=123456789
DM_LOG_CHANNEL_ID=123456789
PEXELS_API_KEY=your_key_here
```

### 3. Get Bot Token

1. Visit [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application → Bot → Add Bot
3. Copy token and paste in `.env`
4. Enable **Server Members Intent** and **Message Content Intent**

### 4. Invite Bot

Replace `CLIENT_ID`:

```
https://discord.com/oauth2/authorize?client_id=CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

### 5. Run

```bash
python bot.py
```

## Customization

Edit `Config` class for cooldowns and rewards:

```python
class Config:
    XP_COOLDOWN = 60              # Seconds between XP
    DAILY_COOLDOWN = 86400        # Daily reward cooldown
    WORK_COOLDOWN = 900           # Work cooldown
    FISH_COOLDOWN = 120           # Fishing cooldown
    
    XP_MIN, XP_MAX = 10, 25
    DAILY_MIN, DAILY_MAX = 500, 1000
    WORK_MIN, WORK_MAX = 100, 300
```

Add fish types:

```python
FISH_TYPES = [
    {'emoji': '🐟', 'name': 'Common Fish', 'value': 50, 'weight': 50},
    # Add yours here
]
```

## Commands

| Command | Description |
|---------|-------------|
| `/rank` | View level and XP |
| `/balance` | Check coins |
| `/daily` | Claim daily reward |
| `/work` | Work for coins |
| `/fish` | Go fishing |
| `/fishbag` | View caught fish |
| `/sellfish <name\|all>` | Sell fish |
| `/gamble <amount>` | Bet coins |
| `/shop` | Browse shop |
| `/buy <id>` | Purchase item |
| `/leaderboard` | Server rankings |
| `/flip` | Flip a coin |
| `/roll` | Roll a dice |
| `/8ball <question>` | Magic 8-ball |
| `/joke` | Random joke |
| `/kitty` | Cat picture |
| `/doggy` | Dog picture |
| `/image <query>` | Search images |
| `/music <song> <artist>` | Search music |

| Admin   | Description |
|---------|-------------|
| `/createitem` | Create a shop item |
| `/deleteitem` | Delete a shop item |
|`/setleaderboard` | Setup a leaderboard |
|`/toggle-notifications` | Turn off yt notifications |


## Deployment

### Render (Free)

1. Fork this repo
2. Create Web Service on [Render](https://render.com)
3. Connect GitHub repo
4. Add environment variables
5. Deploy
6. Make a uptimerobot monitor on its render url

### Railway

1. Deploy from GitHub on [Railway](https://railway.app)
2. Add environment variables

### Self-Host

```bash
nohup python bot.py &
```

## Data Storage

Saves to `botdata.json` and `server_settings.json` every 5 minutes.

## Contributing

Pull requests wanted! Fork the repo, make changes, and submit a PR.

```bash
git checkout -b feature/your-feature
git commit -m 'Add feature'
git push origin feature/your-feature
```

## License

MIT License - free to use, modify, and distribute.

## Support

- **Issues**: [GitHub Issues](https://github.com/chersbobers/ToolyBot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/chersbobers/ToolyBot/discussions)

---

Made by [chersbobers](https://github.com/chersbobers) • [⭐ Star this repo](https://github.com/chersbobers/ToolyBot)