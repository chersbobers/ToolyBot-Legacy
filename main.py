import discord
from discord.ext import commands
import os
import asyncio
import logging
import pathlib
from aiohttp import web, ClientSession
import aiohttp
import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography import fernet
import json
import base64

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('tooly_bot')

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = discord.Bot(intents=intents, auto_sync_commands=True)

# Dashboard configuration
DASHBOARD_CONFIG = {
    'CLIENT_ID': os.getenv('CLIENT_ID'),
    'CLIENT_SECRET': os.getenv('CLIENT_SECRET'),
    'REDIRECT_URI': os.getenv('REDIRECT_URI', 'http://localhost:3000/callback'),
    'SECRET_KEY': os.getenv('SECRET_KEY', fernet.Fernet.generate_key().decode())
}

# --- Web Dashboard ---
async def create_dashboard():
    app = web.Application()
    
    # Setup encrypted sessions
    secret_key = base64.urlsafe_b64decode(DASHBOARD_CONFIG['SECRET_KEY'].encode())
    aiohttp_session.setup(app, EncryptedCookieStorage(secret_key))
    
    # Store bot reference
    app['bot'] = bot
    
    # Routes
    app.router.add_get('/', handle_home)
    app.router.add_get('/login', handle_login)
    app.router.add_get('/callback', handle_callback)
    app.router.add_get('/logout', handle_logout)
    app.router.add_get('/dashboard', handle_dashboard)
    app.router.add_get('/api/guilds', handle_api_guilds)
    app.router.add_get('/api/guild/{guild_id}', handle_api_guild)
    app.router.add_post('/api/guild/{guild_id}/config', handle_api_update_config)
    
    # Add static directory only if it exists
    static_dir = pathlib.Path('dashboard/static')
    if static_dir.exists() and static_dir.is_dir():
        app.router.add_static('/static', 'dashboard/static')
        logger.info('📁 Static directory mounted')
    
    return app

# ... (rest of your handlers - keep them all the same)

# --- Web Server Startup ---
async def start_web_server():
    app = await create_dashboard()
    
    port = int(os.getenv('PORT', 3000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f'🌐 Dashboard running on http://0.0.0.0:{port}')

# --- Discord Bot Events ---
@bot.event
async def on_ready():
    logger.info(f'✅ Logged in as {bot.user}')
    logger.info(f'📊 Connected to {len(bot.guilds)} guilds')
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for /help | Tooly Bot"
        )
    )

    # Start dashboard with error handling
    try:
        await start_web_server()
    except Exception as e:
        logger.error(f'❌ Failed to start web server: {e}')
        logger.info('⚠️ Bot will continue running without dashboard')
    
    logger.info('🚀 All systems operational!')

@bot.event
async def on_application_command_error(ctx, error):
    if isinstance(error, discord.errors.ApplicationCommandInvokeError):
        error = error.original
    
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.respond(
            f'⏳ This command is on cooldown. Try again in {error.retry_after:.1f}s',
            ephemeral=True
        )
    elif isinstance(error, commands.MissingPermissions):
        await ctx.respond('❌ You don\'t have permission to use this command!', ephemeral=True)
    else:
        logger.error(f'Command error: {error}')
        await ctx.respond('❌ An error occurred while executing this command.', ephemeral=True)

# --- Cog Loader ---
def load_cogs():
    cogs = [
        'cogs.leveling',
        'cogs.economy',
        'cogs.fishing',
        'cogs.gambling',
        'cogs.fun',
        'cogs.info',
        'cogs.moderation',
        'cogs.reactions',
        'cogs.music',
        'cogs.youtube'
    ]
    
    for cog in cogs:
        try:
            bot.load_extension(cog)
            logger.info(f'✅ Loaded {cog}')
        except Exception as e:
            logger.error(f'❌ Failed to load {cog}: {e}')

# --- Run Bot ---
if __name__ == '__main__':
    token = os.getenv('TOKEN')
    if not token:
        logger.error('❌ TOKEN environment variable not set!')
        exit(1)
    
    if not DASHBOARD_CONFIG['CLIENT_ID'] or not DASHBOARD_CONFIG['CLIENT_SECRET']:
        logger.warning('⚠️ CLIENT_ID or CLIENT_SECRET not set - dashboard OAuth will not work')

    load_cogs()
    logger.info('🚀 Starting Tooly Bot...')
    bot.run(token)