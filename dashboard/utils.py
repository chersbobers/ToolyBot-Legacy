import aiohttp

async def get_guild_config(db, guild_id):
    """Get guild configuration from database"""
    config = await db.guild_configs.find_one({'guild_id': str(guild_id)})
    if not config:
        # Return default config
        config = {
            'guild_id': str(guild_id),
            'prefix': '!',
            'leveling': {
                'enabled': True,
                'xp_rate': 1.0,
                'xp_min': 15,
                'xp_max': 25,
                'level_up_message': '{user} reached level {level}! 🎉',
                'level_up_channel': None,
                'ignored_channels': [],
                'ignored_roles': []
            },
            'economy': {
                'enabled': True,
                'daily_amount': 100,
                'weekly_amount': 500,
                'currency_name': 'coins',
                'currency_symbol': '🪙',
                'starting_balance': 100
            },
            'moderation': {
                'log_channel': None,
                'auto_mod': False,
                'warn_threshold': 3,
                'mute_role': None
            },
            'welcome': {
                'enabled': False,
                'channel': None,
                'message': 'Welcome {user} to {server}!'
            },
            'autoroles': []
        }
    return config

async def update_guild_config(db, guild_id, config_data):
    """Update guild configuration in database"""
    await db.guild_configs.update_one(
        {'guild_id': str(guild_id)},
        {'$set': config_data},
        upsert=True
    )

async def get_guild_stats(db, bot, guild_id):
    """Get guild statistics"""
    stats = {
        'total_members': 0,
        'total_xp_earned': 0,
        'total_commands_used': 0,
        'active_users': 0,
        'total_economy': 0
    }
    
    # Get member count from bot
    guild = bot.get_guild(int(guild_id))
    if guild:
        stats['total_members'] = guild.member_count
    
    # Get stats from database
    users = await db.users.count_documents({'guild_id': str(guild_id)})
    stats['active_users'] = users
    
    # Total XP
    xp_pipeline = [
        {'$match': {'guild_id': str(guild_id)}},
        {'$group': {'_id': None, 'total': {'$sum': '$xp'}}}
    ]
    xp_sum = await db.users.aggregate(xp_pipeline).to_list(1)
    if xp_sum:
        stats['total_xp_earned'] = xp_sum[0]['total']
    
    # Total economy
    balance_pipeline = [
        {'$match': {'guild_id': str(guild_id)}},
        {'$group': {'_id': None, 'total': {'$sum': '$balance'}}}
    ]
    balance_sum = await db.users.aggregate(balance_pipeline).to_list(1)
    if balance_sum:
        stats['total_economy'] = balance_sum[0]['total']
    
    return stats

async def check_user_permissions(session, guild_id, access_token):
    """Check if user has admin permissions in guild"""
    
    # Get user's guilds
    async with aiohttp.ClientSession() as http_session:
        headers = {'Authorization': f"Bearer {access_token}"}
        async with http_session.get('https://discord.com/api/users/@me/guilds', headers=headers) as resp:
            if resp.status != 200:
                return False
            user_guilds = await resp.json()
    
    # Check if user has admin in this guild
    for guild in user_guilds:
        if guild['id'] == str(guild_id):
            # Check for administrator permission (0x8)
            return (int(guild['permissions']) & 0x8) == 0x8
    
    return False