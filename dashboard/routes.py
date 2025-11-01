from aiohttp import web
from .handlers import (
    handle_home,
    handle_login, 
    handle_callback,
    handle_logout,
    handle_dashboard,
    handle_guild_dashboard
)
from .api_handlers import (
    handle_api_guilds,
    handle_api_guild,
    handle_api_guild_stats,
    handle_api_get_config,
    handle_api_update_config,
    handle_api_leaderboard
)

def setup_routes(app):
    """Setup all dashboard routes"""
    
    # Page routes
    app.router.add_get('/', handle_home)
    app.router.add_get('/login', handle_login)
    app.router.add_get('/callback', handle_callback)
    app.router.add_get('/logout', handle_logout)
    app.router.add_get('/dashboard', handle_dashboard)
    app.router.add_get('/dashboard/{guild_id}', handle_guild_dashboard)  # THIS WAS MISSING
    
    # API routes
    app.router.add_get('/api/guilds', handle_api_guilds)
    app.router.add_get('/api/guild/{guild_id}', handle_api_guild)
    app.router.add_get('/api/guild/{guild_id}/stats', handle_api_guild_stats)
    app.router.add_get('/api/guild/{guild_id}/config', handle_api_get_config)
    app.router.add_post('/api/guild/{guild_id}/config', handle_api_update_config)
    app.router.add_get('/api/guild/{guild_id}/leaderboard', handle_api_leaderboard)