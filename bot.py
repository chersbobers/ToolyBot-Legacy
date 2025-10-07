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
from typing import Optional, Tuple, List
import random
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup

# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord_bot')

# Constants
class Config:
    XP_COOLDOWN = 60
    DAILY_COOLDOWN = 86400
    WORK_COOLDOWN = 900
    FISH_COOLDOWN = 120
    GAMBLE_MIN = 10
    GAMBLE_MAX_PERCENT = 0.5
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
    LEADERBOARD_UPDATE_INTERVAL = 3600
    SETTINGS_FILE = 'server_settings.json'

class BotData:
    def __init__(self):
        self.data = {
            'levels': {},
            'economy': {},
            'warnings': {},
            'lastVideoId': '',
            'leaderboard_messages': {}
        }
        self.load()
    
    def load(self):
        try:
            if os.path.exists(Config.DATA_FILE):
                with open(Config.DATA_FILE, 'r') as f:
                    loaded = json.load(f)
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
        return self.data['economy'].get(user_id, {
            'coins': 0, 
            'bank': 0, 
            'lastDaily': 0, 
            'lastWork': 0,
            'lastFish': 0,
            'fishCaught': 0,
            'totalGambled': 0,
            'gamblingWins': 0,
            'fishInventory': {}  # NEW: Store caught fish
        })
    
    def set_user_economy(self, user_id: str, data: dict):
        self.data['economy'][user_id] = data
    
    def get_warnings(self, user_id: str):
        return self.data['warnings'].get(user_id, [])
    
    def add_warning(self, user_id: str, warning: dict):
        if user_id not in self.data['warnings']:
            self.data['warnings'][user_id] = []
        self.data['warnings'][user_id].append(warning)

def load_server_settings():
    if os.path.exists(Config.SETTINGS_FILE):
        with open(Config.SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_server_settings(settings):
    with open(Config.SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

def get_shop_items(bot_data):
    if 'shop_items' not in bot_data.data:
        bot_data.data['shop_items'] = {}
    return bot_data.data['shop_items']

def get_user_inventory(bot_data, user_id: str):
    if 'inventory' not in bot_data.data:
        bot_data.data['inventory'] = {}
    return bot_data.data['inventory'].get(user_id, {})

def add_to_inventory(bot_data, user_id: str, item_id: str):
    if 'inventory' not in bot_data.data:
        bot_data.data['inventory'] = {}
    if user_id not in bot_data.data['inventory']:
        bot_data.data['inventory'][user_id] = {}
    
    bot_data.data['inventory'][user_id][item_id] = {
        'purchased': datetime.utcnow().timestamp()
    }

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
server_settings = load_server_settings()
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

# ============ FISH TYPES (EXPANDED) ============
FISH_TYPES = [
    {'emoji': '🐟', 'name': 'Common Fish', 'value': 50, 'weight': 50},
    {'emoji': '🐠', 'name': 'Tropical Fish', 'value': 100, 'weight': 30},
    {'emoji': '🦈', 'name': 'Shark', 'value': 300, 'weight': 10},
    {'emoji': '🐙', 'name': 'Octopus', 'value': 200, 'weight': 15},
    {'emoji': '🦀', 'name': 'Crab', 'value': 75, 'weight': 25},
    {'emoji': '🐢', 'name': 'Turtle', 'value': 150, 'weight': 20},
    {'emoji': '🦞', 'name': 'Lobster', 'value': 180, 'weight': 18},
    {'emoji': '🐡', 'name': 'Pufferfish', 'value': 220, 'weight': 12},
    {'emoji': '🦑', 'name': 'Squid', 'value': 140, 'weight': 22},
    {'emoji': '🐋', 'name': 'Whale', 'value': 500, 'weight': 5},
    {'emoji': '🐬', 'name': 'Dolphin', 'value': 350, 'weight': 8},
    {'emoji': '🦭', 'name': 'Seal', 'value': 280, 'weight': 9},
    {'emoji': '🐚', 'name': 'Pearl', 'value': 400, 'weight': 6},
    {'emoji': '⚓', 'name': 'Old Anchor', 'value': 250, 'weight': 8},
    {'emoji': '💎', 'name': 'Diamond', 'value': 1000, 'weight': 2},
    {'emoji': '🏆', 'name': 'Golden Trophy', 'value': 1500, 'weight': 1},
    {'emoji': '👢', 'name': 'Old Boot', 'value': 10, 'weight': 40},
    {'emoji': '🥫', 'name': 'Tin Can', 'value': 5, 'weight': 35},
]

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

@bot.tree.command(name='image', description='Search for an image')
@app_commands.describe(query='What to search for')
async def image(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    try:
        PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')
        if not PEXELS_API_KEY:
            await interaction.followup.send('Pexels API key not set. Please set PEXELS_API_KEY in your environment.')
            return

        url = f'https://api.pexels.com/v1/search?query={query}&per_page=1'
        headers = {'Authorization': PEXELS_API_KEY}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    await interaction.followup.send('Failed to contact Pexels API.')
                    return
                data = await response.json()
                if not data.get('photos'):
                    await interaction.followup.send('No images found for your query.')
                    return
                photo = data['photos'][0]
                image_url = photo['src']['large']
                photographer = photo.get('photographer', 'Unknown')
                photographer_url = photo.get('photographer_url', '')

        embed = discord.Embed(
            title=f'🔍 {query}',
            color=0xFF69B4,
            timestamp=datetime.utcnow(),
            description=f'Photo by [{photographer}]({photographer_url}) on Pexels'
        )
        embed.set_image(url=image_url)
        embed.set_footer(text=f'Requested by {interaction.user.name} • Powered by Pexels')

        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f'Image search error: {e}')
        await interaction.followup.send('Failed to search for images 😥')

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
    embed = generate_leaderboard_embed()
    await interaction.response.send_message(embed=embed)

# ============ ECONOMY COMMANDS ============
@bot.tree.command(name='balance', description='Check your balance')
@app_commands.describe(user='User to check')
async def balance(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    user_id = str(target.id)
    economy_data = bot_data.get_user_economy(user_id)
    embed = discord.Embed(title=f'💰 {target.name}\'s Balance', color=0xFFD700, timestamp=datetime.utcnow())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name='💵 Wallet', value=f'{economy_data["coins"]:,} coins', inline=True)
    embed.add_field(name='🏦 Bank', value=f'{economy_data["bank"]:,} coins', inline=True)
    embed.add_field(name='💎 Total', value=f'{economy_data["coins"] + economy_data["bank"]:,} coins', inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='daily', description='Claim your daily reward')
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    now = datetime.utcnow().timestamp()
    
    if now - economy_data.get('lastDaily', 0) < Config.DAILY_COOLDOWN:
        time_left = Config.DAILY_COOLDOWN - (now - economy_data.get('lastDaily', 0))
        hours = int(time_left // 3600)
        minutes = int((time_left % 3600) // 60)
        await interaction.response.send_message(
            f'⏳ You already claimed your daily! Come back in {hours}h {minutes}m',
            ephemeral=True
        )
        return
    
    reward = random.randint(Config.DAILY_MIN, Config.DAILY_MAX)
    economy_data['coins'] += reward
    economy_data['lastDaily'] = now
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    
    embed = discord.Embed(
        title='🎁 Daily Reward Claimed!',
        description=f'You received **{reward} coins**!',
        color=0x00FF00,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='work', description='Work for coins')
async def work(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    now = datetime.utcnow().timestamp()
    
    if now - economy_data.get('lastWork', 0) < Config.WORK_COOLDOWN:
        time_left = Config.WORK_COOLDOWN - (now - economy_data.get('lastWork', 0))
        minutes = int(time_left // 60)
        await interaction.response.send_message(
            f'⏳ You need to rest! Come back in {minutes}m',
            ephemeral=True
        )
        return
    
    jobs = ['programmer', 'chef', 'teacher', 'doctor', 'artist', 'musician', 'writer', 'engineer']
    job = random.choice(jobs)
    reward = random.randint(Config.WORK_MIN, Config.WORK_MAX)
    economy_data['coins'] += reward
    economy_data['lastWork'] = now
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    
    embed = discord.Embed(
        title=f'💼 You worked as a {job}!',
        description=f'You earned **{reward} coins**!',
        color=0x3498DB,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='shop', description='Browse the shop')
async def shop(interaction: discord.Interaction):
    shop_items = get_shop_items(bot_data)
    
    if not shop_items:
        await interaction.response.send_message('🛒 The shop is empty right now. Check back later!')
        return
    
    embed = discord.Embed(
        title='🛒 Tooly Shop',
        description='Purchase items with your coins!\nUse `/buy <item_id>` to purchase an item.',
        color=0xFF69B4,
        timestamp=datetime.utcnow()
    )
    
    roles = {k: v for k, v in shop_items.items() if v['type'] == 'role'}
    badges = {k: v for k, v in shop_items.items() if v['type'] == 'badge'}
    consumables = {k: v for k, v in shop_items.items() if v['type'] == 'consumable'}
    
    if roles:
        role_text = '\n'.join([
            f"{item['emoji']} **{item['name']}** - {item['price']} coins\n└ {item['description']}\n└ ID: `{item_id}`"
            for item_id, item in roles.items()
        ])
        embed.add_field(name='👑 Roles', value=role_text, inline=False)
    
    if badges:
        badge_text = '\n'.join([
            f"{item['emoji']} **{item['name']}** - {item['price']} coins\n└ {item['description']}\n└ ID: `{item_id}`"
            for item_id, item in badges.items()
        ])
        embed.add_field(name='🏆 Badges', value=badge_text, inline=False)
    
    if consumables:
        consumable_text = '\n'.join([
            f"{item['emoji']} **{item['name']}** - {item['price']} coins\n└ {item['description']}\n└ ID: `{item_id}`"
            for item_id, item in consumables.items()
        ])
        embed.add_field(name='✨ Consumables', value=consumable_text, inline=False)
    
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    embed.set_footer(text=f'Your balance: {economy_data["coins"]} coins | Use /inventory to see owned items')
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='buy', description='Purchase an item from the shop')
@app_commands.describe(item_id='Item ID to purchase (see /shop)')
async def buy(interaction: discord.Interaction, item_id: str):
    shop_items = get_shop_items(bot_data)
    
    if item_id not in shop_items:
        await interaction.response.send_message('❌ Invalid item ID! Use `/shop` to see available items.', ephemeral=True)
        return
    
    item = shop_items[item_id]
    user_id = str(interaction.user.id)
    
    inventory = get_user_inventory(bot_data, user_id)
    if item_id in inventory and item['type'] != 'consumable':
        await interaction.response.send_message(f'❌ You already own **{item["name"]}**!', ephemeral=True)
        return
    
    economy_data = bot_data.get_user_economy(user_id)
    if economy_data['coins'] < item['price']:
        needed = item['price'] - economy_data['coins']
        await interaction.response.send_message(
            f'❌ You need **{needed}** more coins to buy **{item["name"]}**!\nYou have: {economy_data["coins"]} coins',
            ephemeral=True
        )
        return
    
    economy_data['coins'] -= item['price']
    bot_data.set_user_economy(user_id, economy_data)
    add_to_inventory(bot_data, user_id, item_id)
    bot_data.save()
    
    if item['type'] == 'role' and item.get('role_id'):
        try:
            role = interaction.guild.get_role(int(item['role_id']))
            if role:
                await interaction.user.add_roles(role)
        except Exception as e:
            logger.error(f'Error adding role: {e}')
    
    embed = discord.Embed(
        title='✅ Purchase Successful!',
        description=f'You purchased **{item["name"]}**!',
        color=0x00FF00,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name='Item', value=f"{item['emoji']} {item['name']}", inline=True)
    embed.add_field(name='Price', value=f'{item["price"]} coins', inline=True)
    embed.add_field(name='Remaining Balance', value=f'{economy_data["coins"]} coins', inline=True)
    
    if item['type'] == 'role':
        embed.add_field(name='Role Added', value='Check your profile!', inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='inventory', description='View your purchased items')
async def inventory(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    inventory = get_user_inventory(bot_data, user_id)
    shop_items = get_shop_items(bot_data)
    
    if not inventory:
        await interaction.response.send_message('📦 Your inventory is empty! Visit `/shop` to buy items.')
        return
    
    embed = discord.Embed(
        title=f'📦 {interaction.user.name}\'s Inventory',
        color=0x9B59B6,
        timestamp=datetime.utcnow()
    )
    
    for item_id, purchase_data in inventory.items():
        if item_id in shop_items:
            item = shop_items[item_id]
            purchased_date = datetime.fromtimestamp(purchase_data['purchased']).strftime('%Y-%m-%d')
            embed.add_field(
                name=f"{item['emoji']} {item['name']}",
                value=f"{item['description']}\nPurchased: {purchased_date}",
                inline=False
            )
    
    await interaction.response.send_message(embed=embed)

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

@bot.tree.command(name='botinfo', description='Show detailed bot information')
async def botinfo(interaction: discord.Interaction):
    import platform
    import psutil
    import sys
    
    total_users = len(bot_data.data.get('levels', {}))
    total_coins = sum(e.get('coins', 0) + e.get('bank', 0) for e in bot_data.data.get('economy', {}).values())
    total_guilds = len(bot.guilds)
    total_commands = len(bot.tree.get_commands())
    
    process = psutil.Process()
    memory_usage = process.memory_info().rss / 1024 / 1024
    cpu_usage = process.cpu_percent()
    
    embed = discord.Embed(
        title='<:tooly:1364760067706191882> Tooly Bot Information',
        description='A feature-rich Discord bot with leveling, economy, fishing, moderation, and more!',
        color=0x9B59B6,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name='🤖 Bot Name', value=bot.user.name, inline=True)
    embed.add_field(name='🆔 Bot ID', value=str(bot.user.id), inline=True)
    embed.add_field(name='📅 Created', value=bot.user.created_at.strftime('%Y-%m-%d'), inline=True)
    
    embed.add_field(name='<:tooly:1364760067706191882> Version', value='**Beta 1.4**', inline=True)
    embed.add_field(name='🐍 Python', value=f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}', inline=True)
    embed.add_field(name='📚 Discord.py', value=discord.__version__, inline=True)
    
    embed.add_field(name='📊 Servers', value=str(total_guilds), inline=True)
    embed.add_field(name='👥 Tracked Users', value=str(total_users), inline=True)
    embed.add_field(name='💰 Total Economy', value=f'{total_coins:,} coins', inline=True)
    
    embed.add_field(name='💻 Hosting', value='Render Cloud', inline=True)
    embed.add_field(name='🧠 RAM Usage', value=f'{memory_usage:.1f} MB', inline=True)
    embed.add_field(name='⚡ CPU Usage', value=f'{cpu_usage:.1f}%', inline=True)
    
    features = [
        '✅ XP & Leveling System',
        '✅ Economy with Shop',
        '✅ Enhanced Fishing (18 fish types!)',
        '✅ Fish Selling System',
        '✅ Gambling Minigame',
        '✅ Auto-Moderation',
        '✅ YouTube Notifications',
        '✅ Auto-Updating Leaderboards'
    ]
    embed.add_field(name='🎯 Features', value='\n'.join(features), inline=False)
    
    embed.add_field(name='⚙️ Commands', value=f'{total_commands} slash commands', inline=True)
    embed.add_field(name='🏓 Latency', value=f'{round(bot.latency * 1000)}ms', inline=True)
    embed.add_field(name='📈 Status', value='✅ Online', inline=True)
    
    embed.set_footer(text='Made with ❤️ by chersbobers | Use /help for commands')
    
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='userinfo', description='Show user information')
@app_commands.describe(user='User to check')
async def userinfo(interaction: discord.Interaction, user: Optional[discord.Member] = None):
    target = user or interaction.user
    user_id = str(target.id)
    
    level_data = bot_data.get_user_level(user_id)
    economy_data = bot_data.get_user_economy(user_id)
    
    embed = discord.Embed(title='User Information', color=0x9B59B6, timestamp=datetime.utcnow())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name='👤 Username', value=target.name, inline=True)
    embed.add_field(name='🆔 User ID', value=str(target.id), inline=True)
    embed.add_field(name='📅 Account Created', value=target.created_at.strftime('%Y-%m-%d'), inline=False)
    
    if isinstance(target, discord.Member):
        embed.add_field(name='📥 Joined Server', value=target.joined_at.strftime('%Y-%m-%d'), inline=False)
    
    embed.add_field(name='⭐ Level', value=str(level_data['level']), inline=True)
    embed.add_field(name='✨ XP', value=str(level_data['xp']), inline=True)
    embed.add_field(name='💰 Coins', value=f"{economy_data['coins']:,}", inline=True)
    
    if economy_data.get('fishCaught', 0) > 0:
        embed.add_field(name='🎣 Fish Caught', value=str(economy_data['fishCaught']), inline=True)
    
    await interaction.response.send_message(embed=embed)

# ============ LEADERBOARD COMMANDS ============
@bot.tree.command(name='setleaderboard', description='[ADMIN] Set auto-updating leaderboard in this channel')
@app_commands.default_permissions(administrator=True)
async def setleaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    
    embed = generate_leaderboard_embed(str(interaction.guild.id))
    message = await interaction.channel.send(embed=embed)
    
    if 'leaderboard_messages' not in bot_data.data:
        bot_data.data['leaderboard_messages'] = {}
    
    bot_data.data['leaderboard_messages'][str(interaction.guild.id)] = {
        'channel_id': str(interaction.channel.id),
        'message_id': str(message.id)
    }
    bot_data.save()
    
    await interaction.followup.send('✅ Auto-updating leaderboard created! It will update every hour.')

@bot.tree.command(name='toggle-notifications', description='Toggle PippyOC video notifications on/off')
@app_commands.default_permissions(manage_guild=True)
async def toggle_notifications(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    if guild_id not in server_settings:
        server_settings[guild_id] = {'notifications_enabled': True}
    
    current = server_settings[guild_id].get('notifications_enabled', True)
    server_settings[guild_id]['notifications_enabled'] = not current
    
    save_server_settings(server_settings)
    
    status = "enabled ✅" if not current else "disabled ❌"
    
    embed = discord.Embed(
        title='🔔 Notification Settings',
        description=f'PippyOC notifications are now **{status}**',
        color=0xFF69B4 if not current else 0x808080,
        timestamp=datetime.utcnow()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='notification-status', description='Check if notifications are enabled')
async def notification_status(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    enabled = server_settings.get(guild_id, {}).get('notifications_enabled', True)
    
    status = "enabled ✅" if enabled else "disabled ❌"
    
    embed = discord.Embed(
        title='🔔 Notification Status',
        description=f'PippyOC notifications are currently **{status}**',
        color=0xFF69B4 if enabled else 0x808080,
        timestamp=datetime.utcnow()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='roll', description='Roll a dice')
async def roll(interaction: discord.Interaction):
    result = random.randint(1, 6)
    await interaction.response.send_message(f'🎲 You rolled a **{result}**!')

@bot.tree.command(name='music', description='Search for a song')
@app_commands.describe(song='Song name', artist='Artist name')
async def music(interaction: discord.Interaction, song: str, artist: str):
    await interaction.response.defer()
    try:
        async with aiohttp.ClientSession() as session:
            youtube_query = f'{artist} {song} official music video'.replace(' ', '+')
            youtube_search_url = f'https://www.youtube.com/results?search_query={youtube_query}'

            song_clean = re.sub(r'[^a-z0-9]', '', song.lower())
            artist_clean = re.sub(r'[^a-z0-9]', '', artist.lower())
            lyrics_url = f'https://www.azlyrics.com/lyrics/{artist_clean}/{song_clean}.html'

            itunes_url = f'https://itunes.apple.com/search?term={artist}+{song}&entity=song&limit=1'
            async with session.get(itunes_url) as resp:
                itunes_data = await resp.json()

            embed = discord.Embed(
                title=f'🎵 {song}',
                description=f'by **{artist}**',
                color=0xFF69B4,
                timestamp=datetime.utcnow()
            )

            if itunes_data.get('results') and len(itunes_data['results']) > 0:
                result = itunes_data['results'][0]
                album_art = result.get('artworkUrl100', '').replace('100x100', '600x600')
                if album_art:
                    embed.set_thumbnail(url=album_art)
                if result.get('collectionName'):
                    embed.add_field(name='💿 Album', value=result['collectionName'], inline=True)
                if result.get('releaseDate'):
                    year = result['releaseDate'][:4]
                    embed.add_field(name='📅 Year', value=year, inline=True)
                if result.get('trackTimeMillis'):
                    duration = result['trackTimeMillis'] // 1000
                    minutes = duration // 60
                    seconds = duration % 60
                    embed.add_field(name='⏱️ Duration', value=f'{minutes}:{seconds:02d}', inline=True)
                if result.get('trackViewUrl'):
                    embed.add_field(name='🎧 Listen on Apple Music', value=f'[Open in iTunes]({result["trackViewUrl"]})', inline=False)

            embed.add_field(name='📺 Watch on YouTube', value=f'[Search for music video]({youtube_search_url})', inline=False)
            embed.add_field(name='📝 Read Lyrics', value=f'[View on AZLyrics]({lyrics_url})', inline=False)
            embed.set_footer(text=f'Requested by {interaction.user.name}')

            await interaction.followup.send(embed=embed)

    except Exception as e:
        logger.error(f'Music search error: {e}')
        await interaction.followup.send('Failed to find song info 😥')

# ============ FISHING COMMANDS ============
@bot.tree.command(name='fish', description='Go fishing for coins and treasures')
async def fish(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    now = datetime.utcnow().timestamp()
    
    if now - economy_data.get('lastFish', 0) < Config.FISH_COOLDOWN:
        time_left = Config.FISH_COOLDOWN - (now - economy_data.get('lastFish', 0))
        await interaction.response.send_message(
            f'⏳ Your fishing rod needs to rest! Come back in {int(time_left)} seconds.',
            ephemeral=True
        )
        return
    
    total_weight = sum(o['weight'] for o in FISH_TYPES)
    rand = random.uniform(0, total_weight)
    current = 0
    
    for outcome in FISH_TYPES:
        current += outcome['weight']
        if rand <= current:
            catch = outcome
            break
    
    # Store fish in inventory instead of auto-selling
    if 'fishInventory' not in economy_data:
        economy_data['fishInventory'] = {}
    
    fish_key = catch['name']
    if fish_key not in economy_data['fishInventory']:
        economy_data['fishInventory'][fish_key] = {'count': 0, 'emoji': catch['emoji'], 'value': catch['value']}
    
    economy_data['fishInventory'][fish_key]['count'] += 1
    economy_data['lastFish'] = now
    economy_data['fishCaught'] = economy_data.get('fishCaught', 0) + 1
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    
    rarity = '⭐⭐⭐ LEGENDARY' if catch['value'] >= 1000 else '⭐⭐ RARE' if catch['value'] >= 200 else '⭐ UNCOMMON' if catch['value'] >= 100 else 'COMMON'
    
    embed = discord.Embed(
        title='🎣 Fishing Results',
        description=f'You caught a **{catch["name"]}**! {catch["emoji"]}\n\n*Use `/sellfish` to sell your catch!*',
        color=0x00CED1,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name='Value', value=f'{catch["value"]} coins', inline=True)
    embed.add_field(name='Rarity', value=rarity, inline=True)
    embed.add_field(name='Total Fish Caught', value=str(economy_data['fishCaught']), inline=True)
    embed.add_field(name='In Inventory', value=f'{economy_data["fishInventory"][fish_key]["count"]} {catch["name"]}', inline=False)
    embed.set_footer(text=f'Fish again in {Config.FISH_COOLDOWN}s')
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='fishbag', description='View your fish inventory')
async def fishbag(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    fish_inventory = economy_data.get('fishInventory', {})
    
    if not fish_inventory:
        await interaction.response.send_message('🎣 Your fish bag is empty! Use `/fish` to catch some fish!')
        return
    
    embed = discord.Embed(
        title=f'🎣 {interaction.user.name}\'s Fish Bag',
        description='Use `/sellfish all` to sell everything, or `/sellfish <fish_name>` to sell specific fish.',
        color=0x00CED1,
        timestamp=datetime.utcnow()
    )
    
    total_value = 0
    for fish_name, fish_data in sorted(fish_inventory.items(), key=lambda x: x[1]['value'], reverse=True):
        count = fish_data['count']
        value = fish_data['value']
        emoji = fish_data['emoji']
        total = count * value
        total_value += total
        
        embed.add_field(
            name=f'{emoji} {fish_name}',
            value=f'Count: **{count}**\nValue: {value} coins each\nTotal: **{total:,} coins**',
            inline=True
        )
    
    embed.add_field(name='💰 Total Bag Value', value=f'**{total_value:,} coins**', inline=False)
    embed.set_footer(text=f'Total fish caught: {economy_data.get("fishCaught", 0)}')
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='sellfish', description='Sell your caught fish')
@app_commands.describe(fish_name='Name of fish to sell, or "all" to sell everything')
async def sellfish(interaction: discord.Interaction, fish_name: str):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    fish_inventory = economy_data.get('fishInventory', {})
    
    if not fish_inventory:
        await interaction.response.send_message('❌ You don\'t have any fish to sell! Use `/fish` first.', ephemeral=True)
        return
    
    if fish_name.lower() == 'all':
        total_earned = 0
        fish_sold = []
        
        for fish, data in fish_inventory.items():
            count = data['count']
            value = data['value']
            earnings = count * value
            total_earned += earnings
            fish_sold.append(f"{data['emoji']} {fish} x{count} = {earnings:,} coins")
        
        economy_data['coins'] += total_earned
        economy_data['fishInventory'] = {}
        bot_data.set_user_economy(user_id, economy_data)
        bot_data.save()
        
        embed = discord.Embed(
            title='💰 Fish Sold!',
            description=f'You sold all your fish for **{total_earned:,} coins**!',
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Fish Sold', value='\n'.join(fish_sold), inline=False)
        embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=False)
        
        await interaction.response.send_message(embed=embed)
    else:
        # Sell specific fish
        matched_fish = None
        for fish in fish_inventory.keys():
            if fish.lower() == fish_name.lower():
                matched_fish = fish
                break
        
        if not matched_fish:
            await interaction.response.send_message(
                f'❌ You don\'t have any "{fish_name}" in your inventory!\nUse `/fishbag` to see what you have.',
                ephemeral=True
            )
            return
        
        fish_data = fish_inventory[matched_fish]
        count = fish_data['count']
        value = fish_data['value']
        total_earned = count * value
        
        economy_data['coins'] += total_earned
        del economy_data['fishInventory'][matched_fish]
        bot_data.set_user_economy(user_id, economy_data)
        bot_data.save()
        
        embed = discord.Embed(
            title='💰 Fish Sold!',
            description=f'You sold **{count}x {fish_data["emoji"]} {matched_fish}** for **{total_earned:,} coins**!',
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Earned', value=f'{total_earned:,} coins', inline=True)
        embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=True)
        
        await interaction.response.send_message(embed=embed)

# ============ GAMBLING COMMAND ============
@bot.tree.command(name='gamble', description='Gamble coins (max 50% of wallet)')
@app_commands.describe(amount='Amount to gamble')
async def gamble(interaction: discord.Interaction, amount: int):
    user_id = str(interaction.user.id)
    economy_data = bot_data.get_user_economy(user_id)
    
    if amount < Config.GAMBLE_MIN:
        await interaction.response.send_message(
            f'❌ Minimum bet is {Config.GAMBLE_MIN} coins!',
            ephemeral=True
        )
        return
    
    max_bet = int(economy_data['coins'] * Config.GAMBLE_MAX_PERCENT)
    if amount > max_bet:
        await interaction.response.send_message(
            f'❌ You can only gamble up to 50% of your wallet ({max_bet} coins)!',
            ephemeral=True
        )
        return
    
    if amount > economy_data['coins']:
        await interaction.response.send_message(
            '❌ You don\'t have enough coins!',
            ephemeral=True
        )
        return
    
    won = random.random() < 0.47
    
    if won:
        winnings = int(amount * random.uniform(1.5, 2.5))
        economy_data['coins'] += winnings
        economy_data['gamblingWins'] = economy_data.get('gamblingWins', 0) + 1
        
        embed = discord.Embed(
            title='🎰 Jackpot!',
            description=f'You won **{winnings} coins**!',
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Bet', value=f'{amount} coins', inline=True)
        embed.add_field(name='Won', value=f'{winnings} coins', inline=True)
        embed.add_field(name='New Balance', value=f'{economy_data["coins"]} coins', inline=True)
    else:
        economy_data['coins'] -= amount
        
        embed = discord.Embed(
            title='🎰 Lost!',
            description=f'You lost **{amount} coins**...',
            color=0xFF0000,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Lost', value=f'{amount} coins', inline=True)
        embed.add_field(name='Remaining', value=f'{economy_data["coins"]} coins', inline=True)
    
    economy_data['totalGambled'] = economy_data.get('totalGambled', 0) + amount
    bot_data.set_user_economy(user_id, economy_data)
    bot_data.save()
    
    embed.set_footer(text='⚠️ Gamble responsibly! Max 50% of wallet per bet.')
    await interaction.response.send_message(embed=embed)

# ============ ADMIN COMMANDS ============
@bot.tree.command(name='createitem', description='[ADMIN] Create a new shop item')
@app_commands.describe(
    item_id='Unique ID for the item',
    name='Display name',
    price='Price in coins',
    description='Item description',
    emoji='Emoji for the item',
    item_type='Type: role, badge, or consumable',
    role_id='Role ID (only for role type items)'
)
@app_commands.default_permissions(administrator=True)
async def createitem(
    interaction: discord.Interaction,
    item_id: str,
    name: str,
    price: int,
    description: str,
    emoji: str,
    item_type: str,
    role_id: Optional[str] = None
):
    if price < 1:
        await interaction.response.send_message('❌ Price must be at least 1 coin!', ephemeral=True)
        return
    
    if item_type not in ['role', 'badge', 'consumable']:
        await interaction.response.send_message('❌ Item type must be: role, badge, or consumable', ephemeral=True)
        return
    
    if item_type == 'role' and not role_id:
        await interaction.response.send_message('❌ Role items require a role_id!', ephemeral=True)
        return
    
    shop_items = get_shop_items(bot_data)
    if item_id in shop_items:
        await interaction.response.send_message(f'❌ Item with ID `{item_id}` already exists!', ephemeral=True)
        return
    
    shop_items[item_id] = {
        'name': name[:100],
        'description': description[:200],
        'price': price,
        'emoji': emoji[:10],
        'type': item_type,
        'role_id': role_id,
        'created': datetime.utcnow().timestamp(),
        'creator': str(interaction.user.id)
    }
    
    bot_data.data['shop_items'] = shop_items
    bot_data.save()
    
    embed = discord.Embed(
        title='✅ Item Created Successfully',
        color=0x00FF00,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name='ID', value=f'`{item_id}`', inline=True)
    embed.add_field(name='Name', value=name, inline=True)
    embed.add_field(name='Price', value=f'{price} coins', inline=True)
    embed.add_field(name='Type', value=item_type, inline=True)
    embed.add_field(name='Emoji', value=emoji, inline=True)
    if role_id:
        embed.add_field(name='Role ID', value=role_id, inline=True)
    embed.add_field(name='Description', value=description, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='deleteitem', description='[ADMIN] Delete a shop item')
@app_commands.describe(item_id='ID of item to delete')
@app_commands.default_permissions(administrator=True)
async def deleteitem(interaction: discord.Interaction, item_id: str):
    shop_items = get_shop_items(bot_data)
    
    if item_id not in shop_items:
        await interaction.response.send_message(f'❌ Item `{item_id}` not found!', ephemeral=True)
        return
    
    item = shop_items[item_id]
    del shop_items[item_id]
    bot_data.data['shop_items'] = shop_items
    bot_data.save()
    
    await interaction.response.send_message(f'✅ Deleted item: **{item["name"]}** (`{item_id}`)')

@bot.tree.command(name='listitems', description='[ADMIN] List all shop items with IDs')
@app_commands.default_permissions(administrator=True)
async def listitems(interaction: discord.Interaction):
    shop_items = get_shop_items(bot_data)
    
    if not shop_items:
        await interaction.response.send_message('📦 No items in shop yet. Use `/createitem` to add some!', ephemeral=True)
        return
    
    embed = discord.Embed(
        title='📋 All Shop Items (Admin View)',
        color=0x9B59B6,
        timestamp=datetime.utcnow()
    )
    
    for item_id, item in shop_items.items():
        field_value = f"**Price:** {item['price']} coins\n**Type:** {item['type']}\n**Description:** {item['description']}"
        if item.get('role_id'):
            field_value += f"\n**Role ID:** {item['role_id']}"
        
        embed.add_field(
            name=f"{item['emoji']} {item['name']} (`{item_id}`)",
            value=field_value,
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============ EVENT HANDLERS ============
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=" for /help to be typed"))
    try:
        synced = await bot.tree.sync()
        logger.info(f'Synced {len(synced)} commands')
    except Exception as e:
        logger.error(f'Failed to sync commands: {e}')
    autosave.start()
    check_videos.start()
    update_leaderboard.start()
    await start_web_server()

@bot.event
async def on_member_join(member: discord.Member):
    if member.bot:
        return
    welcome_msg = f"""👋 Welcome to **{member.guild.name}**, {member.name}!

I'm Tooly Bot! Here's what I can do:
• 📊 Earn XP and level up by chatting
• 💰 Economy system with daily rewards
• 🎣 Go fishing and sell your catch
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

    is_blocked = AutoMod.check_inappropriate(message.content)
    if is_blocked:
        try:
            await message.delete()
            await message.channel.send(
                f'⚠️ {message.author.mention}, your message was removed for inappropriate content',
                delete_after=5
            )
            logger.info(f'Blocked message from {message.author}')
        except discord.Forbidden:
            logger.warning('Missing permissions to delete message')
        return

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
            await message.channel.send(
                f'{random.choice(messages)} You earned **{coin_reward} coins**! 💰'
            )
        
        bot_data.set_user_level(user_id, user_data)
        bot_data.save()

    content_lower = message.content.lower()
    if any(name.lower() in content_lower for name in ['clanka', 'clanker', 'tinskin']):
        cooldown_key = f'{message.author.id}-{message.channel.id}'
        now = datetime.utcnow().timestamp()
        
        if cooldown_key in name_mention_cooldowns:
            if now - name_mention_cooldowns[cooldown_key] < Config.NAME_MENTION_COOLDOWN:
                await bot.process_commands(message)
                return
        
        name_mention_cooldowns[cooldown_key] = now
        responses = [
            'Robophobia in the big 25', 'Woah you cant say that', 'DONT SLUR AT ME!', '@Pippy ban them',
            'ROBOPHOBIA wow real cool dude', 'how would you like it if i called you a human?', 'beep boop',
            'BEEP BOOP', 'BEEP BOOP BEEP BOOP', 'BEEP BOOP BEEP BOOP BEEP BOOP', 'DING DONG',
            'DING DONG DING DONG', 'DING DONG DING DONG DING DONG', 'DONG DING', 'DONG DING DONG DING',
            'DONG DING DONG DING DONG DING', 'DINGA LINGA LOO', 'DINGA LINGA LOO LOO',
            'DOO WOP A DOO WOP A DOO WOP', 'DOO WOP A DOO WOP A DOO WOP A DOO WOP',
            'BOP A DOO WOP A BOP A DOO WOP', 'BOP A DOO WOP A BOP A DOO WOP A BOP A DOO WOP'
        ]
        await message.reply(random.choice(responses))
    
    await bot.process_commands(message)

# ============ BACKGROUND TASKS ============
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
                    guild_id = str(channel.guild.id)
                    if not server_settings.get(guild_id, {}).get('notifications_enabled', True):
                        logger.info(f'Notifications disabled for guild {guild_id}')
                        bot_data.data['lastVideoId'] = video_id
                        bot_data.save()
                        return

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
                    pub_date = datetime.strptime(latest.published, '%Y-%m-%dT%H:%M:%S%z')
                    embed.add_field(name='Published', value=pub_date.strftime('%Y-%m-%d %H:%M'), inline=True)
                    await channel.send('📺 New video alert!', embed=embed)
            bot_data.data['lastVideoId'] = video_id
            bot_data.save()
    except Exception as e:
        logger.error(f'Error checking videos: {e}')

@tasks.loop(seconds=Config.LEADERBOARD_UPDATE_INTERVAL)
async def update_leaderboard():
    try:
        for guild_id, msg_data in bot_data.data.get('leaderboard_messages', {}).items():
            channel = bot.get_channel(int(msg_data['channel_id']))
            if not channel:
                continue
                
            try:
                message = await channel.fetch_message(int(msg_data['message_id']))
                embed = generate_leaderboard_embed(guild_id)
                await message.edit(embed=embed)
                logger.info(f'Updated leaderboard for guild {guild_id}')
            except discord.NotFound:
                del bot_data.data['leaderboard_messages'][guild_id]
                bot_data.save()
            except Exception as e:
                logger.error(f'Error updating leaderboard: {e}')
    except Exception as e:
        logger.error(f'Leaderboard update error: {e}')

def generate_leaderboard_embed(guild_id: str = None):
    # Sort by level first, then XP
    all_users = sorted(bot_data.data['levels'].items(), key=lambda x: (x[1]['level'], x[1]['xp']), reverse=True)[:10]
    
    description = []
    for i, (user_id, data) in enumerate(all_users):
        medal = '🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'**{i+1}.**'
        
        # Get economy data for this user
        economy_data = bot_data.get_user_economy(user_id)
        total_coins = economy_data.get('coins', 0) + economy_data.get('bank', 0)
        
        # Format: Rank | User | Level (XP) | Total Coins
        description.append(
            f'{medal} <@{user_id}>\n'
            f'└ Level {data["level"]} ({data["xp"]} XP) • {total_coins:,} coins'
        )
    
    embed = discord.Embed(
        title='🏆 Server Leaderboard',
        description='\n'.join(description) if description else 'No users yet!',
        color=0x9B59B6,
        timestamp=datetime.utcnow()
    )
    embed.set_footer(text='Updates every hour • Showing Level & Total Coins')
    return embed

if __name__ == '__main__':
    token = os.getenv('TOKEN')
    if not token:
        logger.error('❌ TOKEN environment variable not set!')
        exit(1)
    bot.run(token)