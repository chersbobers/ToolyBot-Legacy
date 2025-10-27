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

bot = discord.Bot(intents=intents)

# ---------- Web Server ---------- #
async def start_web_server():
    async def handle(request):
        return web.Response(text="Tooly Bot is online!")
    
    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_head('/', handle)  # Add HEAD support for health checks
    
    runner = web.AppRunner(app)
    await runner.setup()
    # Use PORT environment variable (Render uses 3000 by default)
    port = int(os.getenv('PORT', 3000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f'🌐 Web server running on port {port}')

# ---------- Events ---------- #
@bot.event
async def on_ready():
    logger.info(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info(f'📊 Connected to {len(bot.guilds)} guilds')
    
    # Manually sync commands
    try:
        synced = await bot.sync_commands()
        logger.info(f'✅ Synced {len(synced)} slash commands')
    except Exception as e:
        logger.error(f'❌ Failed to sync commands: {e}')
    
    # Set bot presence
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="for /help | Tooly Bot"
        )
    )
    
    # Start web server
    try:
        await start_web_server()
    except Exception as e:
        logger.error(f'❌ Failed to start web server: {e}')
    
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
        await ctx.respond(
            '❌ You don\'t have permission to use this command!',
            ephemeral=True
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.respond(
            f'❌ Missing required argument: {error.param.name}',
            ephemeral=True
        )
    else:
        logger.error(f'Command error in {ctx.command}: {error}', exc_info=True)
        try:
            await ctx.respond(
                '❌ An error occurred while executing this command.',
                ephemeral=True
            )
        except:
            pass  # Command might have already responded

@bot.event
async def on_connect():
    logger.info('🔗 Bot connected to Discord')

@bot.event
async def on_disconnect():
    logger.warning('⚠️ Bot disconnected from Discord')

@bot.event
async def on_resumed():
    logger.info('♻️ Bot session resumed')

# ---------- Load Cogs ---------- #
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
            logger.error(f'❌ Failed to load {cog}: {e}', exc_info=True)

# ---------- Main ---------- #
if __name__ == '__main__':
    token = os.getenv('TOKEN')
    if not token:
        logger.error('❌ TOKEN environment variable not set!')
        exit(1)
    
    load_cogs()
    logger.info('🚀 Starting Tooly Bot...')
    bot.run(token)