from aiohttp import web, ClientSession
import aiohttp_session

async def handle_login(request):
    """Redirect to Discord OAuth"""
    config = request.app['config']
    oauth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={config['CLIENT_ID']}"
        f"&redirect_uri={config['REDIRECT_URI']}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return web.Response(status=302, headers={'Location': oauth_url})

async def handle_callback(request):
    """Handle OAuth callback from Discord"""
    code = request.query.get('code')
    if not code:
        return web.Response(text="Error: No code provided", status=400)
    
    config = request.app['config']
    
    # Exchange code for token
    async with ClientSession() as session:
        data = {
            'client_id': config['CLIENT_ID'],
            'client_secret': config['CLIENT_SECRET'],
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': config['REDIRECT_URI']
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
    """Clear session and logout"""
    session = await aiohttp_session.get_session(request)
    session.clear()
    return web.Response(status=302, headers={'Location': '/'})