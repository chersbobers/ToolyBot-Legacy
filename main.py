import discord
from discord.ext import commands
import os
import asyncio
import logging
from aiohttp import web

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

# Web server for dashboard
async def start_web_server():
    from dashboard import create_app
    app = create_app(bot)
    port = int(os.getenv('PORT', 3000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f'🌐 Dashboard running on port {port}')

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
    
    await start_web_server()
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

# Load all cogs
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

if __name__ == '__main__':
    token = os.getenv('TOKEN')
    if not token:
        logger.error('❌ TOKEN environment variable not set!')
        exit(1)
    
    load_cogs()
    logger.info('🚀 Starting Tooly Bot...')
    bot.run(token)