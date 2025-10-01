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
import random

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord_bot')

# Constants
class Config:
    XP_COOLDOWN = 60
    DAILY_COOLDOWN = 86400
    WORK_COOLDOWN = 3600
    NAME_MENTION_COOLDOWN = 30
    
    XP_MIN, XP_MAX = 10, 25
    XP_PER_LEVEL = 100
    DAILY_MIN, DAILY_MAX = 500, 1000
    WORK_MIN, WORK_MAX = 100, 300
    LEVEL_UP_MULTIPLIER = 50
    
    WARN_THRESHOLD = 3
    TIMEOUT_DURATION = 60
    
    DATA_FILE = 'botdata.json'
    AUTOSAVE_INTERVAL = 300
    VIDEO_CHECK_INTERVAL = 300

class BotData:
    def __init__(self):
        self.data = {
            'levels': {},
            'economy': {},
            'warnings': {},
            'lastVideoId': ''
        }
        self.load()
    
    def load(self):
        try:
            if os.path.exists(Config.DATA_FILE):
                with open(Config.DATA_FILE, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle missing keys
                    self.data.update(loaded)
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

class AutoMod:
    @staticmethod
    def normalize_text(text: str) -> str:
        normalized = text.lower()
        normalized = re.sub(r'\s+', '', normalized)
        normalized = re.sub(r'[^a-z0-9]', '', normalized)
        replacements = {'0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '8': 'b'}
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        return normalized
    
    @staticmethod
    def check_inappropriate(content: str) -> bool:
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

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)
bot_data = BotData()
name_mention_cooldowns = {}

# Web server
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
                embed = discord.Embed(title='📩 DM Received', description=message.content, color=0x3498DB, timestamp=datetime.utcnow())
                embed.set_footer(text=f'From: {message.author} ({message.author.id})')
                await channel.send(embed=embed)
        return
    
    # Automod
    automod_enabled = os.getenv('AUTOMOD_ENABLED', 'true').lower() == 'true'
    if automod_enabled and AutoMod.check_inappropriate(message.content):
        try:
            await message.delete()
            user_id = str(message.author.id)
            warning = {'reason': 'Automod: Inappropriate language detected', 'mod': str(bot.user.id), 'timestamp': datetime.utcnow().timestamp()}
            bot_data.add_warning(user_id, warning)
            bot_data.save()
            warnings = bot_data.get_warnings(user_id)
            warn_count = len(warnings)
            warn_msg = await message.channel.send(f'⚠️ {message.author.mention}, your message was removed for inappropriate content. Warning {warn_count}/{Config.WARN_THRESHOLD}')
            await asyncio.sleep(5)
            await warn_msg.delete()
            if warn_count >= Config.WARN_THRESHOLD:
                try:
                    duration = timedelta(minutes=Config.TIMEOUT_DURATION)
                    await message.author.timeout(duration, reason=f'Automod: {Config.WARN_THRESHOLD} warnings reached')
                    await message.channel.send(f'🔇 {message.author.mention} has been timed out for {Config.TIMEOUT_DURATION} minutes due to repeated violations.')
                except:
                    pass
            log_channel_id = os.getenv('AUTOMOD_LOG_CHANNEL')
            if log_channel_id:
                log_channel = bot.get_channel(int(log_channel_id))
                if log_channel:
                    embed = discord.Embed(title='🛡️ Automod Action', color=0xFF0000, timestamp=datetime.utcnow())
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
        xp_gain = random.randint(Config.XP_MIN, Config.XP_MAX)
        user_data['xp'] += xp_gain
        xp_needed = user_data['level'] * Config.XP_PER_LEVEL
        if user_data['xp'] >= xp_needed:
            user_data['level'] += 1
            user_data['xp'] = 0
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
            await message.channel.send(f'{random.choice(messages)} You earned **{coin_reward} coins**! 💰')
        bot_data.set_user_level(user_id, user_data)
        bot_data.save()
    
    # Name mentions
    content_lower = message.content.lower()
    if any(name in content_lower for name in ['clanka', 'clanker', 'tinskin', 'Clanka', 'Clanker', 'Tinskin', 'CLANKA', 'CLANKER', 'TINSKIN']):
        cooldown_key = f'{message.author.id}-{message.channel.id}'
        now = datetime.utcnow().timestamp()
        if cooldown_key in name_mention_cooldowns:
            if now - name_mention_cooldowns[cooldown_key] < Config.NAME_MENTION_COOLDOWN:
                return
        name_mention_cooldowns[cooldown_key] = now
        responses = ['Robophobia in the big 25', 'Woah you cant say', 'DONT SLUR AT ME!', '@Pippy ban them', 'ROBOPHOBIA wow real cool dude', 'how would you like it if i called you a human?', 'beep boop', 'BEEP BOOP', 'BEEP BOOP BEEP BOOP', 'BEEP BOOP BEEP BOOP BEEP BOOP', 'DING DONG', 'DING DONG DING DONG', 'DING DONG DING DONG DING DONG', 'DONG DING', 'DONG DING DONG DING', 'DONG DING DONG DING DONG DING', 'DINGA LINGA LOO', 'DINGA LINGA LOO LOO', 'DOO WOP A DOO WOP A DOO WOP', 'DOO WOP A DOO WOP A DOO WOP A DOO WOP', 'BOP A DOO WOP A BOP A DOO WOP', 'BOP A DOO WOP A BOP A DOO WOP A BOP A DOO WOP']
        await message.reply(random.choice(responses))

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
                    embed = discord.Embed(title='🎬 New PippyOC Video!', description=f'**{latest.title}**', url=latest.link, color=0xFF0000, timestamp=datetime.utcnow())
                    if hasattr(latest, 'media_thumbnail'):
                        embed.set_thumbnail(url=latest.media_thumbnail[0]['url'])
                    embed.add_field(name='Channel', value=latest.author, inline=True)
                    pub_date = datetime.strptime(latest.published, '%Y-%m-%dT%H:%M:%S%z')
                    embed.add_field(name='Published', value=pub_date.strftime('%Y-%m-%d %H:%M'), inline=True)
                    await channel.send('📺 New video alert!', embed=embed)
            bot_data.data['lastVideoId'] = video_id
            bot_data.save()
    except Exception as e:
        logger.error(f'Error checking videos: {e}')

# ============ INFO COMMANDS ============
@bot.tree.command(name='ping', description='Check bot latency')
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f'🏓 Pong! Latency: {round(bot.latency * 1000)}ms')

@bot.tree.command(name='hello', description='Say hello')
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message('Hello! 👋 I\'m Tooly Bot!')

@bot.tree.command(name='serverinfo', description='Show server information')
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=guild.name, color=0x9B59B6, timestamp=datetime.utcnow())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name='👥 Members', value=str(guild.member_count), inline=True)
    embed.add_field(name='📅 Created', value=guild.created_at.strftime('%Y-%m-%d'), inline=True)
    embed.add_field(name='🆔 Server ID', value=str(guild.id), inline=True)
    embed.add_field(name='👑 Owner', value=f'<@{guild.owner_id}>', inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='userinfo', description='Show user information')
@app_commands.describe(user='User to check')
async def userinfo(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    embed = discord.Embed(title='User Information', color=0x9B59B6)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name='👤 Username', value=target.name, inline=True)
    embed.add_field(name='🆔 User ID', value=str(target.id), inline=True)
    embed.add_field(name='📅 Account Created', value=target.created_at.strftime('%Y-%m-%d'), inline=False)
    if isinstance(target, discord.Member):
        embed.add_field(name='📥 Joined Server', value=target.joined_at.strftime('%Y-%m-%d'), inline=False)
    await interaction.response.send_message(embed=embed)

# ============ FUN COMMANDS ============
@bot.tree.command(name='roll', description='Roll a dice')
async def roll(interaction: discord.Interaction):
    result = random.randint(1, 6)
    await interaction.response.send_message(f'🎲 You rolled a **{result}**!')

@bot.tree.command(name='flip', description='Flip a coin')
async def flip(interaction: discord.Interaction):
    result = random.choice(['Heads', 'Tails'])
    await interaction.response.send_message(f'🪙 The coin landed on **{result}**!')

@bot.tree.command(name='8ball', description='Ask the magic 8-ball')
@app_commands.describe(question='Your question')
async def eightball(interaction: discord.Interaction, question: str):
    responses = ['Yes, definitely!', 'No way!', 'Maybe...', 'Ask again later', 'Absolutely!', 'I doubt it', 'Signs point to yes', 'Very doubtful', 'Without a doubt', 'My sources say no', 'Outlook good', 'Cannot predict now']
    await interaction.response.send_message(f'🎱 **{question[:200]}**\n{random.choice(responses)}')

@bot.tree.command(name='kitty', description='Get a random cat picture')
async def kitty(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.thecatapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                embed = discord.Embed(title='🐱 Random Kitty!', color=0xFF69B4, timestamp=datetime.utcnow())
                embed.set_image(url=data[0]['url'])
                await interaction.followup.send(embed=embed)
    except:
        await interaction.followup.send('Failed to fetch a cat picture 😿')
@bot.tree.command(name='doggy', description='Get a random dog picture')
async def Doggy(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.thedogapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                embed = discord.Embed(title='🐶 Random Doggy!', color=0xFF69B4, timestamp=datetime.utcnow())
                embed.set_image(url=data[0]['url'])
                await interaction.followup.send(embed=embed)
    except:
        await interaction.followup.send('Failed to fetch a dog picture 😥')
@bot.tree.command(name='randompet', description='Get a random pet picture')
async def random_pet(interaction: discord.Interaction):
    await interaction.response.defer()
    pet_num = random.randint(1, 2)  
    try:
        async with aiohttp.ClientSession() as session:
            if pet_num == 1:
                async with session.get('https://api.thecatapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    embed = discord.Embed(title='🐱 Random Pet!', color=0xFF69B4, timestamp=datetime.utcnow())
                    embed.set_image(url=data[0]['url'])
                    await interaction.followup.send(embed=embed)
            if pet_num == 2:
                async with session.get('https://api.thedogapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    embed = discord.Embed(title='🐶 Random Pet!', color=0xFF69B4, timestamp=datetime.utcnow())
                    embed.set_image(url=data[0]['url'])
                    await interaction.followup.send(embed=embed)
    except:
        await interaction.followup.send('Failed to fetch a pet picture 😥')

@bot.tree.command(name='joke', description='Get a random joke')
async def joke(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://official-joke-api.appspot.com/random_joke', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                embed = discord.Embed(title='😂 Random Joke', description=f'**{data["setup"]}**\n\n||{data["punchline"]}||', color=0xFFA500, timestamp=datetime.utcnow())
                embed.set_footer(text=f'{data["type"]} joke')
                await interaction.followup.send(embed=embed)
    except:
        jokes = [
            {'setup': 'Why did the scarecrow win an award?', 'punchline': 'Because he was outstanding in his field!'},
            {'setup': 'Why don\'t scientists trust atoms?', 'punchline': 'Because they make up everything!'},
            {'setup': 'What do you call a fake noodle?', 'punchline': 'An impasta!'},
            {'setup': 'Why did the bicycle fall over?', 'punchline': 'Because it was two tired!'},
        ]
        j = random.choice(jokes)
        embed = discord.Embed(title='😂 Random Joke', description=f'**{j["setup"]}**\n\n||{j["punchline"]}||', color=0xFFA500, timestamp=datetime.utcnow())
        await interaction.followup.send(embed=embed)

@bot.tree.command(name='yotsuba', description='Yotsuba picture')
async def yotsuba(interaction: discord.Interaction):
    embed = discord.Embed(title='🍀 Yotsuba!', description='Here\'s a Yotsuba image!', color=0x77DD77, timestamp=datetime.utcnow())
    embed.set_image(url='https://i.ibb.co/BDhQV8B/yotsuba.jpg')
    await interaction.response.send_message(embed=embed)

# ============ LEVEL COMMANDS ============
@bot.tree.command(name='rank', description='Check your rank and level')
@app_commands.describe(user='User to check')
async def rank(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    user_id = str(target.id)
    user_data = bot_data.get_user_level(user_id)
    xp_needed = user_data['level'] * Config.XP_PER_LEVEL
    all_users = sorted(bot_data.data['levels'].items(), key=lambda x: (x[1]['level'], x[1]['xp']), reverse=True)
    rank = next((i + 1 for i, (uid, _) in enumerate(all_users) if uid == user_id), 'Unranked')
    embed = discord.Embed(title=f'📊 {target.name}\'s Rank', color=0x9B59B6, timestamp=datetime.utcnow())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name='🏆 Rank', value=f'#{rank}', inline=True)
    embed.add_field(name='⭐ Level', value=str(user_data['level']), inline=True)
    embed.add_field(name='✨ XP', value=f'{user_data["xp"]}/{xp_needed}', inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='leaderboard', description='View the server leaderboard')
async def leaderboard(interaction: discord.Interaction):
    all_users = sorted(bot_data.data['levels'].items(), key=lambda x: (x[1]['level'], x[1]['xp']), reverse=True)[:10]
    if not all_users:
        await interaction.response.send_message('No one has earned XP yet!')
        return
    description = []
    for i, (user_id, data) in enumerate(all_users):
        medal = '🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'**{i+1}.**'
        description.append(f'{medal} <@{user_id}> - Level {data["level"]} ({data["xp"]} XP)')
    embed = discord.Embed(title='🏆 Server Leaderboard', description='\n'.join(description), color=0x9B59B6, timestamp=datetime.utcnow())
    await interaction.response.send_message(embed=embed)

# ============ ECONOMY COMMANDS ============
@bot.tree.command(name='balance', description='Check your balance')
@app_commands.describe(user='User to check')
async def balance(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    user_id = str(target.id)
    economy_data = bot_data.get_user_economy(user_id)
    embed = discord.Embed(title=f'💰 {target.name}\'s Balance', color=0xFFD700, timestamp=datetime.utcnow())
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
        await interaction.response.send_message(f'⏳ You already claimed your daily! Come back in {hours}h {minutes}m')
        return
    amount = random.randint(Config.DAILY_MIN, Config.DAILY_MAX)
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
    amount = random.randint(Config.WORK_MIN, Config.WORK_MAX)
    economy_data['coins'] += amount
    economy_data['lastWork'] = now
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    jobs = ['worked at a cafe', 'delivered pizzas', 'coded a website', 'walked dogs', 'mowed lawns', 'streamed on Twitch']
    await interaction.response.send_message(f'💼 You {random.choice(jobs)} and earned **{amount} coins**!')

@bot.tree.command(name='deposit', description='Deposit coins to bank')
@app_commands.describe(amount='Amount to deposit')
async def deposit(interaction: discord.Interaction, amount: int):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    if amount < 1:
        await interaction.response.send_message('❌ Amount must be positive!', ephemeral=True)
        return
    if amount > economy_data['coins']:
        await interaction.response.send_message('❌ You don\'t have enough coins!', ephemeral=True)
        return
    economy_data['coins'] -= amount
    economy_data['bank'] += amount
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    await interaction.response.send_message(f'✅ Deposited **{amount} coins** to your bank!')

@bot.tree.command(name='withdraw', description='Withdraw coins from bank')
@app_commands.describe(amount='Amount to withdraw')
async def withdraw(interaction: discord.Interaction, amount: int):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    if amount < 1:
        await interaction.response.send_message('❌ Amount must be positive!', ephemeral=True)
        return
    if amount > economy_data['bank']:
        await interaction.response.send_message('❌ You don\'t have enough coins in your bank!', ephemeral=True)
        return
    economy_data['bank'] -= amount
    economy_data['coins'] += amount
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    await interaction.response.send_message(f'✅ Withdrew **{amount} coins** from your bank!')

@bot.tree.command(name='give', description='Give coins to someone')
@app_commands.describe(user='User to give coins', amount='Amount to give')
async def give(interaction: discord.Interaction, user: discord.Member, amount: int):
    if user.bot:
        await interaction.response.send_message('❌ You can\'t give coins to bots!', ephemeral=True)
        return
    if user.id == interaction.user.id:
        await interaction.response.send_message('❌ You can\'t give coins to yourself!', ephemeral=True)
        return
    if amount < 1:
        await interaction.response.send_message('❌ Amount must be positive!', ephemeral=True)
        return
    sender_id = str(interaction.user.id)
    sender_data = bot_data.get_user_economy(sender_id)
    if amount > sender_data['coins']:
        await interaction.response.send_message('❌ You don\'t have enough coins!', ephemeral=True)
        return
    recipient_id = str(user.id)
    recipient_data = bot_data.get_user_economy(recipient_id)
    sender_data['coins'] -= amount
    recipient_data['coins'] += amount
    bot_data.set_user_economy(sender_id, sender_data)
    bot_data.set_user_economy(recipient_id, recipient_data)
    bot_data.save()
    await interaction.response.send_message(f'✅ Gave **{amount} coins** to {user.mention}!')

# ============ MODERATION COMMANDS ============
@bot.tree.command(name='warn', description='Warn a user')
@app_commands.describe(user='User to warn', reason='Reason for warning')
@app_commands.default_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if user.bot:
        await interaction.response.send_message('❌ Cannot warn bots!', ephemeral=True)
        return
    warning = {'reason': reason[:500], 'mod': str(interaction.user.id), 'timestamp': datetime.utcnow().timestamp()}
    bot_data.add_warning(str(user.id), warning)
    bot_data.save()
    try:
        await user.send(f'⚠️ You have been warned in **{interaction.guild.name}**\n**Reason:** {reason}')
    except:
        pass
    await interaction.response.send_message(f'✅ Warned {user.mention} for: {reason}')

@bot.tree.command(name='warnings', description='Check warnings')
@app_commands.describe(user='User to check')
@app_commands.default_permissions(moderate_members=True)
async def warnings(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    warns = bot_data.get_warnings(str(target.id))
    if not warns:
        await interaction.response.send_message(f'{target.mention} has no warnings!')
        return
    description = []
    for i, w in enumerate(warns):
        date = datetime.fromtimestamp(w['timestamp']).strftime('%Y-%m-%d')
        description.append(f'**{i+1}.** {w["reason"]}\nBy: <@{w["mod"]}> on {date}')
    embed = discord.Embed(title=f'⚠️ {target.name}\'s Warnings ({len(warns)})', description='\n\n'.join(description), color=0xFF0000, timestamp=datetime.utcnow())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='kick', description='Kick a user')
@app_commands.describe(user='User to kick', reason='Reason')
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, user: discord.Member, reason: Optional[str] = 'No reason provided'):
    if not user.guild_permissions < interaction.user.guild_permissions:
        await interaction.response.send_message('❌ Cannot kick this user!', ephemeral=True)
        return
    try:
        await user.kick(reason=reason)
        await interaction.response.send_message(f'✅ Kicked {user.mention} for: {reason}')
    except:
        await interaction.response.send_message('❌ Failed to kick user!', ephemeral=True)

@bot.tree.command(name='ban', description='Ban a user')
@app_commands.describe(user='User to ban', reason='Reason')
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, user: discord.Member, reason: Optional[str] = 'No reason provided'):
    if not user.guild_permissions < interaction.user.guild_permissions:
        await interaction.response.send_message('❌ Cannot ban this user!', ephemeral=True)
        return
    try:
        await user.ban(reason=reason)
        await interaction.response.send_message(f'✅ Banned {user.mention} for: {reason}')
    except:
        await interaction.response.send_message('❌ Failed to ban user!', ephemeral=True)

@bot.tree.command(name='timeout', description='Timeout a user')
@app_commands.describe(user='User to timeout', duration='Duration in minutes', reason='Reason')
@app_commands.default_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, user: discord.Member, duration: int, reason: Optional[str] = 'No reason provided'):
    if duration < 1 or duration > 40320:
        await interaction.response.send_message('❌ Duration must be between 1 and 40320 minutes!', ephemeral=True)
        return
    try:
        await user.timeout(timedelta(minutes=duration), reason=reason)
        await interaction.response.send_message(f'✅ Timed out {user.mention} for {duration} minutes. Reason: {reason}')
    except:
        await interaction.response.send_message('❌ Cannot timeout this user!', ephemeral=True)

@bot.tree.command(name='purge', description='Delete messages')
@app_commands.describe(amount='Number of messages (1-100)')
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message('❌ Amount must be between 1 and 100!', ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f'✅ Deleted {len(deleted)} messages!', ephemeral=True)

# ============ ADMIN COMMANDS ============
@bot.tree.command(name='say', description='Make the bot say something')
@app_commands.describe(message='Message to send')
@app_commands.default_permissions(administrator=True)
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(message[:2000])
    await interaction.followup.send('✅ Message sent!', ephemeral=True)

@bot.tree.command(name='embed', description='Send an embed message')
@app_commands.describe(text='Embed text', image='Image URL', color='Hex color (e.g., #FF0000)')
@app_commands.default_permissions(administrator=True)
async def embed_cmd(interaction: discord.Interaction, text: str, image: Optional[str] = None, color: Optional[str] = '#9B59B6'):
    # Fix hex color validation
    if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
        await interaction.response.send_message('❌ Invalid hex color!', ephemeral=True)
        return
    color_int = int(color.replace('#', ''), 16)
    embed = discord.Embed(description=text[:4096], color=color_int, timestamp=datetime.utcnow())
    if image:
        # Fix image URL validation
        if not re.match(r'^https?://.+\.(jpg|jpeg|png|gif|webp)$', image, re.IGNORECASE):
            await interaction.response.send_message('❌ Invalid image URL!', ephemeral=True)
            return
        embed.set_image(url=image)
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.send(embed=embed)
    await interaction.followup.send('✅ Embed sent!', ephemeral=True)

@bot.tree.command(name='dm', description='Send a DM to a user')
@app_commands.describe(user='User to message', message='Message content')
@app_commands.default_permissions(moderate_members=True)
async def dm(interaction: discord.Interaction, user: discord.Member, message: str):
    try:
        await user.send(f'📬 **Message from tooly**\n\n{message[:2000]}')
        await interaction.response.send_message(f'✅ Message sent to {user.mention}', ephemeral=True)
    except:
        await interaction.response.send_message('❌ Could not send DM. The user may have DMs off.', ephemeral=True)

# ============ YOUTUBE COMMANDS ============
@bot.tree.command(name='checkvideos', description='Check for new PippyOC videos')
@app_commands.default_permissions(manage_guild=True)
async def checkvideos(interaction: discord.Interaction):
    await interaction.response.send_message('Checking for new PippyOC videos... 🔍')
    await check_videos()

# ============ HELP COMMAND ============
@bot.tree.command(name='help', description='Show all commands')
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title='📋 Tooly Bot Commands', description='Here are all my commands organized by category!', color=0x9B59B6, timestamp=datetime.utcnow())
    embed.add_field(name='ℹ️ Info', value='`/hello` `/ping` `/serverinfo` `/userinfo` `/help`', inline=False)
    embed.add_field(name='🎮 Fun', value='`/roll` `/flip` `/8ball` `/kitty` `/joke` `/yotsuba`', inline=False)
    embed.add_field(name='📊 Levels', value='`/rank` `/leaderboard`\nEarn XP by chatting! (1 msg/min)', inline=False)
    embed.add_field(name='💰 Economy', value='`/balance` `/daily` `/work` `/deposit` `/withdraw` `/give`', inline=False)
    embed.add_field(name='🛡️ Moderation', value='`/warn` `/warnings` `/kick` `/ban` `/timeout` `/purge`', inline=False)
    embed.add_field(name='👑 Admin', value='`/say` `/embed` `/dm`', inline=False)
    embed.add_field(name='📺 YouTube', value='`/checkvideos` - Check for new PippyOC videos', inline=False)
    embed.set_footer(text='Type / to see all commands!')
    await interaction.response.send_message(embed=embed)

if __name__ == '__main__':
    token = os.getenv('TOKEN')
    if not token:
        logger.error('❌ TOKEN environment variable not set!')
        exit(1)
    bot.run(token)