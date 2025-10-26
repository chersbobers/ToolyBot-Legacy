import discord
from discord.ext import commands
from discord import option
from datetime import datetime
import random
import logging
from utils.database import bot_data
from utils.config import Config, FISH_TYPES

logger = logging.getLogger('tooly_bot.fishing')

class Fishing(commands.Cog):
    """Fishing system with 18 different fish types"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @discord.slash_command(name='fish', description='Go fishing for coins and treasures')
    async def fish(self, ctx):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        now = datetime.utcnow().timestamp()
        
        if now - economy_data.get('lastFish', 0) < Config.FISH_COOLDOWN:
            time_left = Config.FISH_COOLDOWN - (now - economy_data.get('lastFish', 0))
            await ctx.respond(
                f'⏳ Your fishing rod needs to rest! Come back in **{int(time_left)}s**',
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
        
        if 'fishInventory' not in economy_data:
            economy_data['fishInventory'] = {}
        
        fish_key = catch['name']
        if fish_key not in economy_data['fishInventory']:
            economy_data['fishInventory'][fish_key] = {'count': 0, 'emoji': catch['emoji'], 'value': catch['value']}
        
        economy_data['fishInventory'][fish_key]['count'] += 1
        economy_data['lastFish'] = now
        economy_data['fishCaught'] = economy_data.get('fishCaught', 0) + 1
        bot_data.set_user_economy(guild_id, user_id, economy_data)
        bot_data.save()
        
        rarity = '⭐⭐⭐ LEGENDARY' if catch['value'] >= 1000 else '⭐⭐ RARE' if catch['value'] >= 200 else '⭐ UNCOMMON' if catch['value'] >= 100 else 'COMMON'
        
        embed = discord.Embed(
            title='🎣 Fishing Results',
            description=f'You caught a **{catch["name"]}**! {catch["emoji"]}\n\n*Use `/sellfish` to sell your catch!*',
            color=0x00CED1,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Value', value=f'{catch["value"]:,} coins', inline=True)
        embed.add_field(name='Rarity', value=rarity, inline=True)
        embed.add_field(name='Total Fish Caught', value=str(economy_data['fishCaught']), inline=True)
        embed.add_field(name='In Inventory', value=f'{economy_data["fishInventory"][fish_key]["count"]} {catch["name"]}', inline=False)
        embed.set_footer(text=f'Fish again in {Config.FISH_COOLDOWN}s')
        
        await ctx.respond(embed=embed)
    
    @discord.slash_command(name='fishbag', description='View your fish inventory')
    async def fishbag(self, ctx):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        fish_inventory = economy_data.get('fishInventory', {})
        
        if not fish_inventory:
            await ctx.respond('🎣 Your fish bag is empty! Use `/fish` to catch some fish!')
            return
        
        embed = discord.Embed(
            title=f'🎣 {ctx.author.display_name}\'s Fish Bag',
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
                value=f'Count: **{count}**\nValue: {value:,} coins each\nTotal: **{total:,} coins**',
                inline=True
            )
        
        embed.add_field(name='💰 Total Bag Value', value=f'**{total_value:,} coins**', inline=False)
        embed.set_footer(text=f'Total fish caught: {economy_data.get("fishCaught", 0)}')
        
        await ctx.respond(embed=embed)
    
    @discord.slash_command(name='sellfish', description='Sell your caught fish')
    @option("fish_name", description='Name of fish to sell, or "all" to sell everything')
    async def sellfish(self, ctx, fish_name: str):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        fish_inventory = economy_data.get('fishInventory', {})
        
        if not fish_inventory:
            await ctx.respond('❌ You don\'t have any fish to sell! Use `/fish` first.', ephemeral=True)
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
            bot_data.set_user_economy(guild_id, user_id, economy_data)
            bot_data.save()
            
            embed = discord.Embed(
                title='💰 Fish Sold!',
                description=f'You sold all your fish for **{total_earned:,} coins**!',
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Fish Sold', value='\n'.join(fish_sold), inline=False)
            embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=False)
            
            await ctx.respond(embed=embed)
        else:
            matched_fish = None
            for fish in fish_inventory.keys():
                if fish.lower() == fish_name.lower():
                    matched_fish = fish
                    break
            
            if not matched_fish:
                await ctx.respond(
                    f'❌ You don\'t have any "{fish_name}" in your inventory!\n'
                    f'Use `/fishbag` to see what you have.',
                    ephemeral=True
                )
                return
            
            fish_data = fish_inventory[matched_fish]
            count = fish_data['count']
            value = fish_data['value']
            total_earned = count * value
            
            economy_data['coins'] += total_earned
            del economy_data['fishInventory'][matched_fish]
            bot_data.set_user_economy(guild_id, user_id, economy_data)
            bot_data.save()
            
            embed = discord.Embed(
                title='💰 Fish Sold!',
                description=f'You sold **{count}x {fish_data["emoji"]} {matched_fish}** for **{total_earned:,} coins**!',
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Earned', value=f'{total_earned:,} coins', inline=True)
            embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=True)
            
            await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Fishing(bot))