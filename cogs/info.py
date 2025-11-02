import discord
from discord.ext import commands
from discord import option
from datetime import datetime
from typing import Optional
import platform
import psutil
import logging
from utils.database import bot_data

logger = logging.getLogger('tooly_bot.info')

class Info(commands.Cog):
    """Information commands about bot, server, and users"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @discord.slash_command(name='ping', description='Check bot latency')
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        color = 0x00FF00 if latency < 100 else 0xFFA500 if latency < 200 else 0xFF0000
        
        embed = discord.Embed(
            title='🏓 Pong!',
            description=f'Latency: **{latency}ms**',
            color=color
        )
        await ctx.respond(embed=embed)
    
    @discord.slash_command(name='serverinfo', description='Show server information')
    async def serverinfo(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(title=f'ℹ️ {guild.name}', color=0x9B59B6, timestamp=datetime.utcnow())
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name='👥 Members', value=f'{guild.member_count:,}', inline=True)
        embed.add_field(name='📅 Created', value=guild.created_at.strftime('%Y-%m-%d'), inline=True)
        embed.add_field(name='👑 Owner', value=f'<@{guild.owner_id}>', inline=True)
        embed.add_field(name='🎭 Roles', value=str(len(guild.roles)), inline=True)
        embed.add_field(name='💬 Channels', value=str(len(guild.channels)), inline=True)
        embed.add_field(name='😊 Emojis', value=str(len(guild.emojis)), inline=True)
        embed.add_field(name='🆔 Server ID', value=str(guild.id), inline=False)
        
        await ctx.respond(embed=embed)
    
    @discord.slash_command(name='botinfo', description='Show detailed bot information')
    async def botinfo(self, ctx):
        guild_id = str(ctx.guild.id)
        
        total_users_global = sum(len(guild_data) for guild_data in bot_data.data.get('levels', {}).values())
        total_users_server = len(bot_data.data.get('levels', {}).get(guild_id, {}))
        
        total_coins_global = sum(
            sum(e.get('coins', 0) + e.get('bank', 0) for e in guild_data.values())
            for guild_data in bot_data.data.get('economy', {}).values()
        )
        total_coins_server = sum(
            e.get('coins', 0) + e.get('bank', 0) 
            for e in bot_data.data.get('economy', {}).get(guild_id, {}).values()
        )
        
        total_guilds = len(self.bot.guilds)
        total_commands = len([cmd for cmd in self.bot.walk_application_commands()])
        
        process = psutil.Process()
        memory_usage = process.memory_info().rss / 1024 / 1024
        
        embed = discord.Embed(
            title='🤖 Tooly Bot',
            description='A feature-rich Discord bot with leveling, economy, fishing, and gambling!',
            color=0x9B59B6,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name='📊 Servers', value=f'{total_guilds:,}', inline=True)
        embed.add_field(name='👥 Users (Global)', value=f'{total_users_global:,}', inline=True)
        embed.add_field(name='👤 Users (Server)', value=f'{total_users_server:,}', inline=True)
        
        embed.add_field(name='💰 Economy (Global)', value=f'{total_coins_global:,}', inline=True)
        embed.add_field(name='💵 Economy (Server)', value=f'{total_coins_server:,}', inline=True)
        embed.add_field(name='⚙️ Commands', value=f'{total_commands}', inline=True)
        
        embed.add_field(name='🏓 Latency', value=f'{round(self.bot.latency * 1000)}ms', inline=True)
        embed.add_field(name='🧠 Memory', value=f'{memory_usage:.0f} MB', inline=True)
        
        features = [
            '⭐ XP & Leveling',
            '💵 Economy & Shop',
            '🎣 Fishing (18 types)',
            '🎰 4 Gambling Games',
            '🎭 Reaction Roles',
            '🛡️ Auto-Moderation',
            '📺 YouTube Alerts'
        ]
        embed.add_field(name='✨ Features', value='\n'.join(features), inline=False)
        
        embed.set_footer(text='Made with ❤️ by chersbobers')
        
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        await ctx.respond(embed=embed)
    
    @discord.slash_command(name='userinfo', description='Show user information')
    @option("user", discord.Member, description="User to check (optional)", required=False)
    async def userinfo(self, ctx, user: Optional[discord.Member] = None):
        guild_id = str(ctx.guild.id)
        target = user or ctx.author
        user_id = str(target.id)
        
        level_data = bot_data.get_user_level(guild_id, user_id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        profile_data = bot_data.get_user_profile(guild_id, user_id)
        
        # Use custom name or default display name
        display_name = profile_data.get('customName', target.display_name)
        
        embed = discord.Embed(
            title=f'ℹ️ {display_name}',
            color=0x9B59B6,
            timestamp=datetime.utcnow()
        )
        
        # Use custom pfp or default avatar
        pfp_url = profile_data.get('customPfp', target.display_avatar.url)
        embed.set_thumbnail(url=pfp_url)
        
        embed.add_field(name='👤 Username', value=f'{target.name}#{target.discriminator}', inline=True)
        embed.add_field(name='🆔 User ID', value=str(target.id), inline=True)
        embed.add_field(name='📅 Account Created', value=target.created_at.strftime('%Y-%m-%d'), inline=False)
        
        if isinstance(target, discord.Member):
            embed.add_field(name='📥 Joined Server', value=target.joined_at.strftime('%Y-%m-%d'), inline=False)
        
        embed.add_field(name='⭐ Level', value=str(level_data['level']), inline=True)
        embed.add_field(name='✨ XP', value=f"{level_data['xp']:,}", inline=True)
        embed.add_field(name='💰 Coins', value=f"{economy_data['coins']:,}", inline=True)
        
        if economy_data.get('fishCaught', 0) > 0:
            embed.add_field(name='🎣 Fish Caught', value=f"{economy_data['fishCaught']:,}", inline=True)
        
        if economy_data.get('gamblingWins', 0) > 0:
            embed.add_field(name='🎰 Gambling Wins', value=f"{economy_data['gamblingWins']:,}", inline=True)
        
        await ctx.respond(embed=embed)
    
    @discord.slash_command(name='customize', description='Customize your profile appearance')
    @option("name", str, description="Custom display name (leave blank to reset)", required=False)
    @option("pfp", str, description="Custom profile picture URL (leave blank to reset)", required=False)
    async def customize(self, ctx, name: Optional[str] = None, pfp: Optional[str] = None):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if name is None and pfp is None:
            embed = discord.Embed(
                title='❌ No Changes',
                description='Please provide at least one option to customize!',
                color=0xFF0000
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        
        profile_data = bot_data.get_user_profile(guild_id, user_id)
        changes = []
        
        # Update custom name
        if name is not None:
            if len(name) > 32:
                embed = discord.Embed(
                    title='❌ Name Too Long',
                    description='Custom name must be 32 characters or less!',
                    color=0xFF0000
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            profile_data['customName'] = name
            changes.append(f"**Name:** {name}")
        
        # Update custom pfp
        if pfp is not None:
            # Basic URL validation
            if not (pfp.startswith('http://') or pfp.startswith('https://')):
                embed = discord.Embed(
                    title='❌ Invalid URL',
                    description='Profile picture must be a valid URL starting with http:// or https://',
                    color=0xFF0000
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            
            profile_data['customPfp'] = pfp
            changes.append(f"**Profile Picture:** Set")
        
        bot_data.set_user_profile(guild_id, user_id, profile_data)
        
        embed = discord.Embed(
            title='✅ Profile Customized!',
            description='\n'.join(changes),
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        
        if pfp:
            embed.set_thumbnail(url=pfp)
        
        embed.set_footer(text=f'Use /userinfo to see your customized profile!')
        
        await ctx.respond(embed=embed)
    
    @discord.slash_command(name='customizebot', description='Customize the bot\'s appearance (Admin only)')
    @option("name", str, description="Custom bot display name", required=False)
    @option("pfp", str, description="Custom bot profile picture URL", required=False)
    @discord.default_permissions(administrator=True)
    async def customizebot(self, ctx, name: Optional[str] = None, pfp: Optional[str] = None):
        if name is None and pfp is None:
            embed = discord.Embed(
                title='❌ No Changes',
                description='Please provide at least one option to customize!',
                color=0xFF0000
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        
        changes = []
        
        try:
            # Update bot name
            if name is not None:
                if len(name) > 32:
                    embed = discord.Embed(
                        title='❌ Name Too Long',
                        description='Bot name must be 32 characters or less!',
                        color=0xFF0000
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                await self.bot.user.edit(username=name)
                changes.append(f"**Name:** {name}")
                logger.info(f"Bot name changed to: {name}")
            
            # Update bot pfp
            if pfp is not None:
                # Basic URL validation
                if not (pfp.startswith('http://') or pfp.startswith('https://')):
                    embed = discord.Embed(
                        title='❌ Invalid URL',
                        description='Profile picture must be a valid URL starting with http:// or https://',
                        color=0xFF0000
                    )
                    await ctx.respond(embed=embed, ephemeral=True)
                    return
                
                # Download and set the image
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(pfp) as resp:
                        if resp.status != 200:
                            embed = discord.Embed(
                                title='❌ Failed to Download Image',
                                description='Could not download the image from the provided URL.',
                                color=0xFF0000
                            )
                            await ctx.respond(embed=embed, ephemeral=True)
                            return
                        
                        image_data = await resp.read()
                        await self.bot.user.edit(avatar=image_data)
                        changes.append(f"**Profile Picture:** Updated")
                        logger.info(f"Bot avatar changed")
            
            embed = discord.Embed(
                title='✅ Bot Customized!',
                description='\n'.join(changes),
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            
            if pfp:
                embed.set_thumbnail(url=pfp)
            
            embed.set_footer(text=f'Changes applied successfully!')
            
            await ctx.respond(embed=embed)
            
        except discord.HTTPException as e:
            embed = discord.Embed(
                title='❌ Error',
                description=f'Failed to update bot: {str(e)}',
                color=0xFF0000
            )
            await ctx.respond(embed=embed, ephemeral=True)
            logger.error(f"Error customizing bot: {e}")
    
    @discord.slash_command(name='resetprofile', description='Reset your profile customizations')
    async def resetprofile(self, ctx):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        profile_data = bot_data.get_user_profile(guild_id, user_id)
        
        # Clear custom settings
        profile_data.pop('customName', None)
        profile_data.pop('customPfp', None)
        
        bot_data.set_user_profile(guild_id, user_id, profile_data)
        
        embed = discord.Embed(
            title='✅ Profile Reset!',
            description='Your profile has been reset to default settings.',
            color=0x00FF00
        )
        await ctx.respond(embed=embed, ephemeral=True)

def setup(bot):
    bot.add_cog(Info(bot))