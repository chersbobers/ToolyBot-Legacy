import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import asyncio
import aiohttp
import feedparser
from datetime import datetime, timedelta
import re
from typing import Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord_bot')

# Constants
class Config:
    XP_COOLDOWN = 60  # seconds
    DAILY_COOLDOWN = 86400  # 24 hours
    WORK_COOLDOWN = 3600  # 1 hour
    NAME_MENTION_COOLDOWN = 30
    
    XP_MIN, XP_MAX = 10, 25
    XP_PER_LEVEL = 100
    DAILY_MIN, DAILY_MAX = 500, 1000
    WORK_MIN, WORK_MAX = 100, 300
    LEVEL_UP_MULTIPLIER = 50
    
    WARN_THRESHOLD = 3
    TIMEOUT_DURATION = 60  # minutes
    
    DATA_FILE = 'botdata.json'
    AUTOSAVE_INTERVAL = 300  # 5 minutes
    VIDEO_CHECK_INTERVAL = 300  # 5 minutes

# Data storage
class BotData:
    def __init__(self):
        self.data = {
            'levels': {},
            'economy': {},
            'warnings': {},
            'cooldowns': {},
            'lastVideoId': ''
        }
        self.load()
    
    def load(self):
        try:
            if os.path.exists(Config.DATA_FILE):
                with open(Config.DATA_FILE, 'r') as f:
                    self.data = json.load(f)
                logger.info('Data loaded successfully')
        except Exception as e:
            logger.error(f'Error loading data: {e}')
    
    def save(self):
        try:
            with open(Config.DATA_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f'Error saving data: {e}')
    
    def get_user_level(self, user_id: str):
        return self.data['levels'].get(user_id, {'xp': 0, 'level': 1, 'lastMessage': 0})
    
    def set_user_level(self, user_id: str, data: dict):
        self.data['levels'][user_id] = data
    
    def get_user_economy(self, user_id: str):
        return self.data['economy'].get(user_id, {'coins': 0, 'bank': 0, 'lastDaily': 0, 'lastWork': 0})
    
    def set_user_economy(self, user_id: str, data: dict):
        self.data['economy'][user_id] = data
    
    def get_warnings(self, user_id: str):
        return self.data['warnings'].get(user_id, [])
    
    def add_warning(self, user_id: str, warning: dict):
        if user_id not in self.data['warnings']:
            self.data['warnings'][user_id] = []
        self.data['warnings'][user_id].append(warning)

# Automod
class AutoMod:
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text to detect obfuscated slurs"""
        normalized = text.lower()
        normalized = re.sub(r'\s+', '', normalized)
        normalized = re.sub(r'[^a-z0-9]', '', normalized)
        
        # Leet speak normalization
        replacements = {
            '0': 'o', '1': 'i', '3': 'e', '4': 'a',
            '5': 's', '7': 't', '8': 'b'
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        return normalized
    
    @staticmethod
    def check_inappropriate(content: str) -> bool:
        """Check for inappropriate content"""
        normalized = AutoMod.normalize_text(content)
        
        blocked_patterns = [
            r'n[il]+[gq]+[ea]+r',
            r'n[il]+[gq]+[a]+',
            r'f[a]+[gq]+[gq]?[o]+[t]',
            r'r[e]+[t]+[a]+r?d',
            r'k[il]+k[e]+',
        ]
        
        for pattern in blocked_patterns:
            if re.search(pattern, normalized, re.IGNORECASE):
                return True
        return False

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot_data = BotData()
name_mention_cooldowns = {}

# Web server for Render
from aiohttp import web

async def handle_health(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    
    port = int(os.getenv('PORT', 3000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f'Web server running on port {port}')

# Events
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    
    try:
        synced = await bot.tree.sync()
        logger.info(f'Synced {len(synced)} commands')
    except Exception as e:
        logger.error(f'Failed to sync commands: {e}')
    
    autosave.start()
    check_videos.start()
    
    await start_web_server()

@bot.event
async def on_member_join(member: discord.Member):
    if member.bot:
        return
    
    welcome_msg = f"""👋 Welcome to **{member.guild.name}**, {member.name}!

I'm Tooly Bot! Here's what I can do:
• 📊 Earn XP and level up by chatting
• 💰 Economy system with daily rewards
• 🎮 Fun commands and games
• 🛡️ Moderation tools

Use `/help` to see all commands!"""
    
    try:
        await member.send(welcome_msg)
    except:
        logger.info(f'Could not send DM to {member.name}')

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    
    # Handle DMs
    if isinstance(message.channel, discord.DMChannel):
        dm_log_channel_id = os.getenv('DM_LOG_CHANNEL_ID')
        if dm_log_channel_id:
            channel = bot.get_channel(int(dm_log_channel_id))
            if channel:
                embed = discord.Embed(
                    title='📩 DM Received',
                    description=message.content,
                    color=0x3498DB,
                    timestamp=datetime.utcnow()
                )
                embed.set_footer(text=f'From: {message.author} ({message.author.id})')
                await channel.send(embed=embed)
        return
    
    # Automod
    automod_enabled = os.getenv('AUTOMOD_ENABLED', 'true').lower() == 'true'
    if automod_enabled and AutoMod.check_inappropriate(message.content):
        try:
            await message.delete()
            
            user_id = str(message.author.id)
            warning = {
                'reason': 'Automod: Inappropriate language detected',
                'mod': str(bot.user.id),
                'timestamp': datetime.utcnow().timestamp()
            }
            bot_data.add_warning(user_id, warning)
            bot_data.save()
            
            warnings = bot_data.get_warnings(user_id)
            warn_count = len(warnings)
            
            warn_msg = await message.channel.send(
                f'⚠️ {message.author.mention}, your message was removed for inappropriate content. '
                f'Warning {warn_count}/{Config.WARN_THRESHOLD}'
            )
            await asyncio.sleep(5)
            await warn_msg.delete()
            
            if warn_count >= Config.WARN_THRESHOLD:
                try:
                    duration = timedelta(minutes=Config.TIMEOUT_DURATION)
                    await message.author.timeout(duration, reason=f'Automod: {Config.WARN_THRESHOLD} warnings reached')
                    await message.channel.send(
                        f'🔇 {message.author.mention} has been timed out for {Config.TIMEOUT_DURATION} minutes '
                        f'due to repeated violations.'
                    )
                except:
                    pass
            
            # Log to automod channel
            log_channel_id = os.getenv('AUTOMOD_LOG_CHANNEL')
            if log_channel_id:
                log_channel = bot.get_channel(int(log_channel_id))
                if log_channel:
                    embed = discord.Embed(
                        title='🛡️ Automod Action',
                        color=0xFF0000,
                        timestamp=datetime.utcnow()
                    )
                    embed.add_field(name='User', value=f'{message.author} ({message.author.id})', inline=True)
                    embed.add_field(name='Channel', value=message.channel.mention, inline=True)
                    embed.add_field(name='Content', value=f'||{message.content[:200]}||', inline=False)
                    embed.add_field(name='Warnings', value=f'{warn_count}/{Config.WARN_THRESHOLD}', inline=True)
                    await log_channel.send(embed=embed)
        except Exception as e:
            logger.error(f'Automod error: {e}')
        return
    
    # XP system
    user_id = str(message.author.id)
    user_data = bot_data.get_user_level(user_id)
    now = datetime.utcnow().timestamp()
    
    if now - user_data['lastMessage'] >= Config.XP_COOLDOWN:
        user_data['lastMessage'] = now
        xp_gain = __import__('random').randint(Config.XP_MIN, Config.XP_MAX)
        user_data['xp'] += xp_gain
        
        xp_needed = user_data['level'] * Config.XP_PER_LEVEL
        if user_data['xp'] >= xp_needed:
            user_data['level'] += 1
            user_data['xp'] = 0
            
            # Level up message
            messages = [
                f'🎉 GG {message.author.mention}! You leveled up to **Level {user_data["level"]}**!',
                f'⭐ Congrats {message.author.mention}! You\'re now **Level {user_data["level"]}**!',
                f'🚀 Level up! {message.author.mention} reached **Level {user_data["level"]}**!',
                f'💫 Awesome! {message.author.mention} is now **Level {user_data["level"]}**!'
            ]
            
            coin_reward = user_data['level'] * Config.LEVEL_UP_MULTIPLIER
            economy_data = bot_data.get_user_economy(user_id)
            economy_data['coins'] += coin_reward
            bot_data.set_user_economy(user_id, economy_data)
            
            await message.channel.send(
                f'{__import__("random").choice(messages)} You earned **{coin_reward} coins**! 💰'
            )
        
        bot_data.set_user_level(user_id, user_data)
        bot_data.save()
    
    # Name mention responses
    content_lower = message.content.lower()
    if any(name in content_lower for name in ['tooly', 'toolybot', 'tooly bot']):
        cooldown_key = f'{message.author.id}-{message.channel.id}'
        now = datetime.utcnow().timestamp()
        
        if cooldown_key in name_mention_cooldowns:
            if now - name_mention_cooldowns[cooldown_key] < Config.NAME_MENTION_COOLDOWN:
                return
        
        name_mention_cooldowns[cooldown_key] = now
        
        responses = [
            'Yes? You called? 👀',
            'Tooly reporting for duty! 🫡',
            'Hey there! Need something? Use `/help` to see what I can do!',
            'That\'s me! How can I help? 😊',
            'You rang? 🔔',
            'Hi! I\'m here! Type `/help` for commands! 👋'
        ]
        
        await message.reply(__import__('random').choice(responses))

# Tasks
@tasks.loop(seconds=Config.AUTOSAVE_INTERVAL)
async def autosave():
    bot_data.save()
    logger.info('Data autosaved')

@tasks.loop(seconds=Config.VIDEO_CHECK_INTERVAL)
async def check_videos():
    channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
    notif_channel_id = os.getenv('NOTIFICATION_CHANNEL_ID')
    
    if not channel_id or not notif_channel_id:
        return
    
    try:
        feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
        feed = await asyncio.to_thread(feedparser.parse, feed_url)
        
        if feed.entries:
            latest = feed.entries[0]
            video_id = latest.id
            
            if video_id != bot_data.data['lastVideoId'] and bot_data.data['lastVideoId']:
                channel = bot.get_channel(int(notif_channel_id))
                if channel:
                    embed = discord.Embed(
                        title='🎬 New PippyOC Video!',
                        description=f'**{latest.title}**',
                        url=latest.link,
                        color=0xFF0000,
                        timestamp=datetime.utcnow()
                    )
                    
                    if hasattr(latest, 'media_thumbnail'):
                        embed.set_thumbnail(url=latest.media_thumbnail[0]['url'])
                    
                    embed.add_field(name='Channel', value=latest.author, inline=True)
                    embed.add_field(
                        name='Published',
                        value=datetime.strptime(latest.published, '%Y-%m-%dT%H:%M:%S%z').strftime('%Y-%m-%d %H:%M'),
                        inline=True
                    )
                    
                    await channel.send('📺 New video alert!', embed=embed)
            
            bot_data.data['lastVideoId'] = video_id
            bot_data.save()
    except Exception as e:
        logger.error(f'Error checking videos: {e}')

# Commands
@bot.tree.command(name='ping', description='Check bot latency')
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f'🏓 Pong! Latency: {round(bot.latency * 1000)}ms')

@bot.tree.command(name='hello', description='Say hello')
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message('Hello! 👋 I\'m Tooly Bot!')

@bot.tree.command(name='serverinfo', description='Show server information')
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(
        title=guild.name,
        color=0x9B59B6,
        timestamp=datetime.utcnow()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name='👥 Members', value=str(guild.member_count), inline=True)
    embed.add_field(name='📅 Created', value=guild.created_at.strftime('%Y-%m-%d'), inline=True)
    embed.add_field(name='🆔 Server ID', value=str(guild.id), inline=True)
    embed.add_field(name='👑 Owner', value=f'<@{guild.owner_id}>', inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='rank', description='Check your rank and level')
@app_commands.describe(user='User to check')
async def rank(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    user_id = str(target.id)
    user_data = bot_data.get_user_level(user_id)
    xp_needed = user_data['level'] * Config.XP_PER_LEVEL
    
    # Calculate rank
    all_users = sorted(
        bot_data.data['levels'].items(),
        key=lambda x: (x[1]['level'], x[1]['xp']),
        reverse=True
    )
    rank = next((i + 1 for i, (uid, _) in enumerate(all_users) if uid == user_id), 'Unranked')
    
    embed = discord.Embed(
        title=f'📊 {target.name}\'s Rank',
        color=0x9B59B6,
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name='🏆 Rank', value=f'#{rank}', inline=True)
    embed.add_field(name='⭐ Level', value=str(user_data['level']), inline=True)
    embed.add_field(name='✨ XP', value=f'{user_data["xp"]}/{xp_needed}', inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='balance', description='Check your balance')
@app_commands.describe(user='User to check')
async def balance(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    user_id = str(target.id)
    economy_data = bot_data.get_user_economy(user_id)
    
    embed = discord.Embed(
        title=f'💰 {target.name}\'s Balance',
        color=0xFFD700,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name='🪙 Wallet', value=f'{economy_data["coins"]} coins', inline=True)
    embed.add_field(name='🏦 Bank', value=f'{economy_data["bank"]} coins', inline=True)
    embed.add_field(name='💵 Total', value=f'{economy_data["coins"] + economy_data["bank"]} coins', inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='daily', description='Claim your daily coins')
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    now = datetime.utcnow().timestamp()
    
    if now - economy_data['lastDaily'] < Config.DAILY_COOLDOWN:
        time_left = Config.DAILY_COOLDOWN - (now - economy_data['lastDaily'])
        hours = int(time_left // 3600)
        minutes = int((time_left % 3600) // 60)
        await interaction.response.send_message(
            f'⏳ You already claimed your daily! Come back in {hours}h {minutes}m'
        )
        return
    
    amount = __import__('random').randint(Config.DAILY_MIN, Config.DAILY_MAX)
    economy_data['coins'] += amount
    economy_data['lastDaily'] = now
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    
    await interaction.response.send_message(f'✅ You claimed your daily reward of **{amount} coins**! 💰')

@bot.tree.command(name='work', description='Work for coins')
async def work(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    now = datetime.utcnow().timestamp()
    
    if now - economy_data.get('lastWork', 0) < Config.WORK_COOLDOWN:
        time_left = Config.WORK_COOLDOWN - (now - economy_data.get('lastWork', 0))
        minutes = int(time_left // 60)
        await interaction.response.send_message(f'⏳ You need to wait {minutes} more minutes before working again!')
        return
    
    amount = __import__('random').randint(Config.WORK_MIN, Config.WORK_MAX)
    economy_data['coins'] += amount
    economy_data['lastWork'] = now
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    
    jobs = [
        'worked at a cafe', 'delivered pizzas', 'coded a website',
        'walked dogs', 'mowed lawns', 'streamed on Twitch'
    ]
    
    await interaction.response.send_message(
        f'💼 You {__import__("random").choice(jobs)} and earned **{amount} coins**!'
    )

@bot.tree.command(name='help', description='Show all commands')
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title='📋 Tooly Bot Commands',
        description='Here are all my commands organized by category!',
        color=0x9B59B6,
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name='ℹ️ Info',
        value='`/hello` `/ping` `/serverinfo` `/help`',
        inline=False
    )
    embed.add_field(
        name='📊 Levels',
        value='`/rank` `/leaderboard`\nEarn XP by chatting! (1 msg/min)',
        inline=False
    )
    embed.add_field(
        name='💰 Economy',
        value='`/balance` `/daily` `/work` `/deposit` `/withdraw` `/give`',
        inline=False
    )
    embed.set_footer(text='Type / to see all commands!')
    
    await interaction.response.send_message(embed=embed)

# Run bot
if __name__ == '__main__':
    token = os.getenv('TOKEN')
    if not token:
        logger.error('TOKEN environment variable not set!')
        exit(1)
    
    bot.run(token)