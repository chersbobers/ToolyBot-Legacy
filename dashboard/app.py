from aiohttp import web
import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import base64
import os
from .routes import setup_routes

async def create_dashboard(bot, db):
    """Create and configure the dashboard web application"""
    app = web.Application()
    
    # Setup encrypted sessions
    secret_key = base64.urlsafe_b64decode(os.getenv('SECRET_KEY').encode())
    aiohttp_session.setup(app, EncryptedCookieStorage(secret_key))
    
    # Store bot and database references
    app['bot'] = bot
    app['db'] = db
    app['config'] = {
        'CLIENT_ID': os.getenv('CLIENT_ID'),
        'CLIENT_SECRET': os.getenv('CLIENT_SECRET'),
        'REDIRECT_URI': os.getenv('REDIRECT_URI', 'http://localhost:3000/callback')
    }
    
    # Setup all routes
    setup_routes(app)
    
    return app