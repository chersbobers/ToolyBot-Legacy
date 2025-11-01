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

async def handle_home(request):
    session = await aiohttp_session.get_session(request)
    logged_in = 'user' in session
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tooly Bot Dashboard</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .container {{
                background: white;
                padding: 3rem;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 500px;
            }}
            h1 {{ color: #333; margin-bottom: 1rem; font-size: 2.5rem; }}
            p {{ color: #666; margin-bottom: 2rem; font-size: 1.1rem; }}
            .btn {{
                display: inline-block;
                padding: 1rem 2rem;
                background: #5865F2;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: bold;
                transition: all 0.3s;
            }}
            .btn:hover {{
                background: #4752C4;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(88,101,242,0.4);
            }}
            .features {{
                margin-top: 2rem;
                text-align: left;
            }}
            .feature {{
                padding: 0.5rem 0;
                color: #555;
            }}
            .feature::before {{
                content: "✓ ";
                color: #5865F2;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛠️ Tooly Bot</h1>
            <p>Powerful Discord bot management dashboard</p>
            {"<a href='/dashboard' class='btn'>Go to Dashboard</a>" if logged_in else "<a href='/login' class='btn'>Login with Discord</a>"}
            <div class="features">
                <div class="feature">Leveling System Configuration</div>
                <div class="feature">Economy Settings</div>
                <div class="feature">Moderation Tools</div>
                <div class="feature">Custom Commands</div>
                <div class="feature">Real-time Statistics</div>
            </div>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def handle_login(request):
    oauth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={DASHBOARD_CONFIG['CLIENT_ID']}"
        f"&redirect_uri={DASHBOARD_CONFIG['REDIRECT_URI']}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return web.Response(status=302, headers={'Location': oauth_url})

async def handle_callback(request):
    code = request.query.get('code')
    if not code:
        return web.Response(text="Error: No code provided", status=400)
    
    # Exchange code for token
    async with ClientSession() as session:
        data = {
            'client_id': DASHBOARD_CONFIG['CLIENT_ID'],
            'client_secret': DASHBOARD_CONFIG['CLIENT_SECRET'],
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DASHBOARD_CONFIG['REDIRECT_URI']
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        async with session.post('https://discord.com/api/oauth2/token', data=data, headers=headers) as resp:
            if resp.status != 200:
                return web.Response(text="Error exchanging code", status=400)
            token_data = await resp.json()
        
        # Get user info
        headers = {'Authorization': f"Bearer {token_data['access_token']}"}
        async with session.get('https://discord.com/api/users/@me', headers=headers) as resp:
            user_data = await resp.json()
    
    # Store in session
    session_data = await aiohttp_session.get_session(request)
    session_data['user'] = user_data
    session_data['access_token'] = token_data['access_token']
    
    return web.Response(status=302, headers={'Location': '/dashboard'})

async def handle_logout(request):
    session = await aiohttp_session.get_session(request)
    session.clear()
    return web.Response(status=302, headers={'Location': '/'})

async def handle_dashboard(request):
    session = await aiohttp_session.get_session(request)
    if 'user' not in session:
        return web.Response(status=302, headers={'Location': '/login'})
    
    user = session['user']
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Tooly Bot - Dashboard</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f5f5f5;
            }}
            .navbar {{
                background: #5865F2;
                color: white;
                padding: 1rem 2rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .navbar h1 {{ font-size: 1.5rem; }}
            .user-info {{
                display: flex;
                align-items: center;
                gap: 1rem;
            }}
            .user-avatar {{
                width: 40px;
                height: 40px;
                border-radius: 50%;
            }}
            .btn {{
                padding: 0.5rem 1rem;
                background: white;
                color: #5865F2;
                text-decoration: none;
                border-radius: 5px;
                border: none;
                cursor: pointer;
                font-weight: bold;
            }}
            .container {{
                max-width: 1200px;
                margin: 2rem auto;
                padding: 0 2rem;
            }}
            .guilds-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 1.5rem;
                margin-top: 2rem;
            }}
            .guild-card {{
                background: white;
                padding: 1.5rem;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                transition: transform 0.2s;
            }}
            .guild-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            }}
            .guild-icon {{
                width: 60px;
                height: 60px;
                border-radius: 50%;
                margin-bottom: 1rem;
            }}
            .guild-name {{
                font-size: 1.2rem;
                font-weight: bold;
                margin-bottom: 0.5rem;
            }}
            .guild-btn {{
                display: inline-block;
                margin-top: 1rem;
                padding: 0.5rem 1rem;
                background: #5865F2;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                width: 100%;
                text-align: center;
            }}
            .loading {{
                text-align: center;
                padding: 3rem;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="navbar">
            <h1>🛠️ Tooly Bot Dashboard</h1>
            <div class="user-info">
                <img class="user-avatar" src="https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" alt="Avatar">
                <span>{user['username']}</span>
                <a href="/logout" class="btn">Logout</a>
            </div>
        </div>
        
        <div class="container">
            <h2>Select a Server</h2>
            <div class="guilds-grid" id="guilds">
                <div class="loading">Loading your servers...</div>
            </div>
        </div>
        
        <script>
            async function loadGuilds() {{
                const response = await fetch('/api/guilds');
                const guilds = await response.json();
                
                const container = document.getElementById('guilds');
                container.innerHTML = '';
                
                guilds.forEach(guild => {{
                    const card = document.createElement('div');
                    card.className = 'guild-card';
                    
                    const iconUrl = guild.icon 
                        ? `https://cdn.discordapp.com/icons/${{guild.id}}/${{guild.icon}}.png`
                        : 'https://cdn.discordapp.com/embed/avatars/0.png';
                    
                    card.innerHTML = `
                        <img class="guild-icon" src="${{iconUrl}}" alt="${{guild.name}}">
                        <div class="guild-name">${{guild.name}}</div>
                        <div style="color: #666; font-size: 0.9rem;">${{guild.member_count || 'Unknown'}} members</div>
                        ${{guild.bot_in_guild 
                            ? `<a href="/dashboard/${{guild.id}}" class="guild-btn">Manage Server</a>`
                            : `<a href="https://discord.com/api/oauth2/authorize?client_id={DASHBOARD_CONFIG['CLIENT_ID']}&permissions=8&scope=bot%20applications.commands&guild_id=${{guild.id}}" class="guild-btn">Add Bot</a>`
                        }}
                    `;
                    
                    container.appendChild(card);
                }});
            }}
            
            loadGuilds();
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def handle_api_guilds(request):
    session = await aiohttp_session.get_session(request)
    if 'user' not in session:
        return web.json_response({'error': 'Not authenticated'}, status=401)
    
    # Get user's guilds from Discord
    async with ClientSession() as http_session:
        headers = {'Authorization': f"Bearer {session['access_token']}"}
        async with http_session.get('https://discord.com/api/users/@me/guilds', headers=headers) as resp:
            user_guilds = await resp.json()
    
    # Filter guilds where user has admin permissions
    admin_guilds = [g for g in user_guilds if (int(g['permissions']) & 0x8) == 0x8]
    
    # Check which guilds have the bot
    bot = request.app['bot']
    for guild in admin_guilds:
        guild['bot_in_guild'] = bot.get_guild(int(guild['id'])) is not None
    
    return web.json_response(admin_guilds)

async def handle_api_guild(request):
    session = await aiohttp_session.get_session(request)
    if 'user' not in session:
        return web.json_response({'error': 'Not authenticated'}, status=401)
    
    guild_id = int(request.match_info['guild_id'])
    bot = request.app['bot']
    guild = bot.get_guild(guild_id)
    
    if not guild:
        return web.json_response({'error': 'Guild not found'}, status=404)
    
    return web.json_response({
        'id': str(guild.id),
        'name': guild.name,
        'member_count': guild.member_count,
        'icon': guild.icon.url if guild.icon else None
    })

async def handle_api_update_config(request):
    session = await aiohttp_session.get_session(request)
    if 'user' not in session:
        return web.json_response({'error': 'Not authenticated'}, status=401)
    
    guild_id = request.match_info['guild_id']
    data = await request.json()
    
    # Here you would save configuration to your database
    # For now, just return success
    logger.info(f"Updated config for guild {guild_id}: {data}")
    
    return web.json_response({'success': True})

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

    # Start dashboard
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