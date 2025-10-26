import discord
from discord.ext import commands
from discord import option
from datetime import datetime
from typing import Optional
import random
import logging

from utils.database import bot_data
from utils.config import Config

logger = logging.getLogger('tooly_bot.economy')


class Economy(commands.Cog):
    """Economy system with daily rewards, work, and shop."""

    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name='createitem', description='[ADMIN] Create a new shop item')
    @option("item_id", description="Unique ID for the item")
    @option("name", description="Display name")
    @option("price", description="Price in coins", min_value=1)
    @option("description", description="Item description")
    @option("emoji", description="Emoji for the item")
    @option("item_type", description="Type of item", choices=["role", "badge", "consumable"])
    @option("role_id", description="Role ID (only for role type items)", required=False)
    @discord.default_permissions(administrator=True)
    async def createitem(
        self,
        ctx,
        item_id: str,
        name: str,
        price: int,
        description: str,
        emoji: str,
        item_type: str,
        role_id: str = None
    ):
        guild_id = str(ctx.guild.id)
        
        if item_type == 'role' and not role_id:
            await ctx.respond('❌ Role items require a role_id!', ephemeral=True)
            return

        if 'shop_items' not in bot_data.data:
            bot_data.data['shop_items'] = {}
        if guild_id not in bot_data.data['shop_items']:
            bot_data.data['shop_items'][guild_id] = {}
            
        shop_items = bot_data.data['shop_items'][guild_id]
        
        if item_id in shop_items:
            await ctx.respond(f'❌ Item with ID `{item_id}` already exists!', ephemeral=True)
            return

        shop_items[item_id] = {
            'name': name[:100],
            'description': description[:200],
            'price': price,
            'emoji': emoji[:10],
            'type': item_type,
            'role_id': role_id,
            'created': datetime.utcnow().timestamp(),
            'creator': str(ctx.author.id)
        }

        bot_data.data['shop_items'][guild_id] = shop_items
        bot_data.save()

        embed = discord.Embed(
            title='✅ Item Created Successfully',
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='ID', value=f'`{item_id}`', inline=True)
        embed.add_field(name='Name', value=name, inline=True)
        embed.add_field(name='Price', value=f'{price:,} coins', inline=True)
        embed.add_field(name='Type', value=item_type, inline=True)
        embed.add_field(name='Emoji', value=emoji, inline=True)
        if role_id:
            embed.add_field(name='Role ID', value=role_id, inline=True)
        embed.add_field(name='Description', value=description, inline=False)

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name='deleteitem', description='[ADMIN] Delete a shop item')
    @option("item_id", description="ID of item to delete")
    @discord.default_permissions(administrator=True)
    async def deleteitem(self, ctx, item_id: str):
        guild_id = str(ctx.guild.id)
        shop_items = bot_data.get_shop_items(guild_id)

        if item_id not in shop_items:
            await ctx.respond(f'❌ Item `{item_id}` not found!', ephemeral=True)
            return

        item = shop_items[item_id]
        del shop_items[item_id]
        bot_data.data['shop_items'][guild_id] = shop_items
        bot_data.save()

        await ctx.respond(f'✅ Deleted item: **{item["name"]}** (`{item_id}`)', ephemeral=True)

    @discord.slash_command(name='listitems', description='[ADMIN] List all shop items with IDs')
    @discord.default_permissions(administrator=True)
    async def listitems(self, ctx):
        guild_id = str(ctx.guild.id)
        shop_items = bot_data.get_shop_items(guild_id)

        if not shop_items:
            await ctx.respond('📦 No items in shop yet. Use `/createitem` to add some!', ephemeral=True)
            return

        embed = discord.Embed(
            title='📋 All Shop Items (Admin View)',
            color=0x9B59B6,
            timestamp=datetime.utcnow()
        )

        for item_id, item in shop_items.items():
            field_value = f"**Price:** {item['price']:,} coins\n**Type:** {item['type']}\n**Description:** {item['description']}"
            if item.get('role_id'):
                field_value += f"\n**Role ID:** {item['role_id']}"

            embed.add_field(
                name=f"{item['emoji']} {item['name']} (`{item_id}`)",
                value=field_value,
                inline=False
            )

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name='balance', description='Check your balance')
    @option("user", discord.Member, description="User to check (optional)", required=False)
    async def balance(self, ctx, user: Optional[discord.Member] = None):
        guild_id = str(ctx.guild.id)
        target = user or ctx.author
        user_id = str(target.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)

        embed = discord.Embed(
            title=f'💰 {target.display_name}\'s Balance',
            color=0xFFD700,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name='💵 Wallet', value=f'{economy_data["coins"]:,} coins', inline=True)
        embed.add_field(name='🏦 Bank', value=f'{economy_data["bank"]:,} coins', inline=True)
        embed.add_field(
            name='💎 Total',
            value=f'{economy_data["coins"] + economy_data["bank"]:,} coins',
            inline=True
        )

        await ctx.respond(embed=embed)

    @discord.slash_command(name='daily', description='Claim your daily reward')
    async def daily(self, ctx):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        now = datetime.utcnow().timestamp()

        if now - economy_data.get('lastDaily', 0) < Config.DAILY_COOLDOWN:
            time_left = Config.DAILY_COOLDOWN - (now - economy_data.get('lastDaily', 0))
            hours = int(time_left // 3600)
            minutes = int((time_left % 3600) // 60)
            await ctx.respond(
                f'⏳ You already claimed your daily! Come back in **{hours}h {minutes}m**',
                ephemeral=True
            )
            return

        reward = random.randint(Config.DAILY_MIN, Config.DAILY_MAX)
        economy_data['coins'] += reward
        economy_data['lastDaily'] = now
        bot_data.set_user_economy(guild_id, user_id, economy_data)
        bot_data.save()

        embed = discord.Embed(
            title='🎁 Daily Reward Claimed!',
            description=f'You received **{reward:,} coins**!',
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=False)
        await ctx.respond(embed=embed)

    @discord.slash_command(name='work', description='Work for coins')
    async def work(self, ctx):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        now = datetime.utcnow().timestamp()

        if now - economy_data.get('lastWork', 0) < Config.WORK_COOLDOWN:
            time_left = Config.WORK_COOLDOWN - (now - economy_data.get('lastWork', 0))
            minutes = int(time_left // 60)
            await ctx.respond(
                f'⏳ You need to rest! Come back in **{minutes}m**',
                ephemeral=True
            )
            return

        jobs = [
            'programmer', 'chef', 'teacher', 'doctor', 'artist',
            'musician', 'writer', 'engineer', 'designer', 'scientist'
        ]
        job = random.choice(jobs)
        reward = random.randint(Config.WORK_MIN, Config.WORK_MAX)
        economy_data['coins'] += reward
        economy_data['lastWork'] = now
        bot_data.set_user_economy(guild_id, user_id, economy_data)
        bot_data.save()

        embed = discord.Embed(
            title=f'💼 You worked as a {job}!',
            description=f'You earned **{reward:,} coins**!',
            color=0x3498DB,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=False)
        await ctx.respond(embed=embed)

    @discord.slash_command(name='shop', description='Browse the shop')
    async def shop(self, ctx):
        guild_id = str(ctx.guild.id)
        shop_items = bot_data.get_shop_items(guild_id)

        if not shop_items:
            await ctx.respond('🛒 The shop is empty right now. Check back later!')
            return

        embed = discord.Embed(
            title='🛒 Tooly Shop',
            description='Purchase items with your coins!\nUse `/buy <item_id>` to purchase.',
            color=0xFF69B4,
            timestamp=datetime.utcnow()
        )

        roles = {k: v for k, v in shop_items.items() if v['type'] == 'role'}
        badges = {k: v for k, v in shop_items.items() if v['type'] == 'badge'}
        consumables = {k: v for k, v in shop_items.items() if v['type'] == 'consumable'}

        if roles:
            role_text = '\n'.join([
                f"{item['emoji']} **{item['name']}** - {item['price']:,} coins\n"
                f"└ {item['description']}\n└ ID: `{item_id}`"
                for item_id, item in roles.items()
            ])
            embed.add_field(name='👑 Roles', value=role_text, inline=False)

        if badges:
            badge_text = '\n'.join([
                f"{item['emoji']} **{item['name']}** - {item['price']:,} coins\n"
                f"└ {item['description']}\n└ ID: `{item_id}`"
                for item_id, item in badges.items()
            ])
            embed.add_field(name='🏆 Badges', value=badge_text, inline=False)

        if consumables:
            consumable_text = '\n'.join([
                f"{item['emoji']} **{item['name']}** - {item['price']:,} coins\n"
                f"└ {item['description']}\n└ ID: `{item_id}`"
                for item_id, item in consumables.items()
            ])
            embed.add_field(name='✨ Consumables', value=consumable_text, inline=False)

        user_id = str(ctx.author.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        embed.set_footer(
            text=f'Your balance: {economy_data["coins"]:,} coins | Use /inventory to see owned items'
        )

        await ctx.respond(embed=embed)

    @discord.slash_command(name='buy', description='Purchase an item from the shop')
    @option("item_id", str, description="Item ID to purchase (see /shop)")
    async def buy(self, ctx, item_id: str):
        guild_id = str(ctx.guild.id)
        shop_items = bot_data.get_shop_items(guild_id)

        if item_id not in shop_items:
            await ctx.respond('❌ Invalid item ID! Use `/shop` to see available items.', ephemeral=True)
            return

        item = shop_items[item_id]
        user_id = str(ctx.author.id)

        inventory = bot_data.get_user_inventory(guild_id, user_id)
        if item_id in inventory and item['type'] != 'consumable':
            await ctx.respond(f'❌ You already own **{item["name"]}**!', ephemeral=True)
            return

        economy_data = bot_data.get_user_economy(guild_id, user_id)
        if economy_data['coins'] < item['price']:
            needed = item['price'] - economy_data['coins']
            await ctx.respond(
                f'❌ You need **{needed:,}** more coins to buy **{item["name"]}**!',
                ephemeral=True
            )
            return

        economy_data['coins'] -= item['price']
        bot_data.set_user_economy(guild_id, user_id, economy_data)
        bot_data.add_to_inventory(guild_id, user_id, item_id)
        bot_data.save()

        if item['type'] == 'role' and item.get('role_id'):
            role = ctx.guild.get_role(int(item['role_id']))
            if role:
                if ctx.guild.me.top_role.position > role.position:
                    try:
                        await ctx.author.add_roles(role, reason="Purchased from shop")
                    except discord.Forbidden:
                        logger.warning(f"Missing permission to add role: {role.name}")
                        await ctx.respond(
                            f'⚠️ I don't have permission to give **{role.name}**. Check my role position!',
                            ephemeral=True
                        )
                else:
                    await ctx.respond(
                        f'⚠️ My highest role is below **{role.name}**, so I can't assign it!',
                        ephemeral=True
                    )

        embed = discord.Embed(
            title='✅ Purchase Successful!',
            description=f'You purchased **{item["name"]}**!',
            color=0x00FF00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Item', value=f"{item['emoji']} {item['name']}", inline=True)
        embed.add_field(name='Price', value=f'{item["price"]:,} coins', inline=True)
        embed.add_field(name='Remaining Balance', value=f'{economy_data["coins"]:,} coins', inline=True)

        if item['type'] == 'role':
            embed.add_field(name='Role Added', value='✅ (If I have permission)', inline=False)

        await ctx.respond(embed=embed)

    @discord.slash_command(name='inventory', description='View your purchased items')
    async def inventory(self, ctx):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        inventory = bot_data.get_user_inventory(guild_id, user_id)
        shop_items = bot_data.get_shop_items(guild_id)

        if not inventory:
            await ctx.respond('📦 Your inventory is empty! Visit `/shop` to buy items.')
            return

        embed = discord.Embed(
            title=f'📦 {ctx.author.display_name}\'s Inventory',
            color=0x9B59B6,
            timestamp=datetime.utcnow()
        )

        for item_id, purchase_data in inventory.items():
            if item_id in shop_items:
                item = shop_items[item_id]
                purchased_date = datetime.fromtimestamp(
                    purchase_data['purchased']
                ).strftime('%Y-%m-%d')
                embed.add_field(
                    name=f"{item['emoji']} {item['name']}",
                    value=f"{item['description']}\nPurchased: {purchased_date}",
                    inline=False
                )

        await ctx.respond(embed=embed)

    @discord.slash_command(name='give', description='Give coins to a user or everyone (Admin only)')
    @discord.default_permissions(administrator=True)
    @option("user", discord.Member, description="User to give coins to (ignored if 'everyone' is true)", required=False)
    @option("everyone", bool, description="Give to everyone in the server", required=False, default=False)
    @option("amount", int, description="Amount of coins to give", required=True)
    async def give(self, ctx, amount: int, user: discord.Member = None, everyone: bool = False):
        guild_id = str(ctx.guild.id)
        
        if amount <= 0:
            await ctx.respond("❌ Amount must be greater than zero.", ephemeral=True)
            return

        if everyone:
            members = [m for m in ctx.guild.members if not m.bot]
            count = 0
            for member in members:
                user_id = str(member.id)
                economy_data = bot_data.get_user_economy(guild_id, user_id)
                economy_data['coins'] += amount
                bot_data.set_user_economy(guild_id, user_id, economy_data)
                count += 1
            bot_data.save()

            embed = discord.Embed(
                title="💸 Global Giveaway!",
                description=f"Gave **{amount:,} coins** to **everyone** ({count} members)!",
                color=0xF1C40F,
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text=f'Given by {ctx.author.display_name}')
            await ctx.respond(embed=embed)
            return

        if not user:
            await ctx.respond("❌ You must specify a user or set `everyone` to True.", ephemeral=True)
            return

        user_id = str(user.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        economy_data['coins'] += amount
        bot_data.set_user_economy(guild_id, user_id, economy_data)
        bot_data.save()

        embed = discord.Embed(
            title='💸 Coins Given!',
            description=f'Gave **{amount:,} coins** to {user.mention}',
            color=0x2ECC71,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='New Balance', value=f'{economy_data["coins"]:,} coins', inline=True)
        embed.set_footer(text=f'Given by {ctx.author.display_name}')
        await ctx.respond(embed=embed)

    @discord.slash_command(name='reseteconomy', description='[ADMIN] Reset ALL economy data for this server')
    @discord.default_permissions(administrator=True)
    async def reseteconomy(self, ctx):
        guild_id = str(ctx.guild.id)
        
        view = discord.ui.View()
        
        async def confirm_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Only the command user can confirm this!", ephemeral=True)
                return
                
            if guild_id in bot_data.data.get('economy', {}):
                del bot_data.data['economy'][guild_id]
            if guild_id in bot_data.data.get('inventory', {}):
                del bot_data.data['inventory'][guild_id]
            bot_data.save()
            
            embed = discord.Embed(
                title='✅ Economy Reset Complete',
                description='All user coins, banks, and inventories have been wiped for this server.',
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        
        async def cancel_callback(interaction):
            if interaction.user.id != ctx.author.id:
                await interaction.response.send_message("❌ Only the command user can cancel this!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title='❌ Reset Cancelled',
                description='Economy data was not reset.',
                color=0x808080,
                timestamp=datetime.utcnow()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        
        confirm_button = discord.ui.Button(label="✅ Confirm Reset", style=discord.ButtonStyle.danger)
        confirm_button.callback = confirm_callback
        
        cancel_button = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
        cancel_button.callback = cancel_callback
        
        view.add_item(confirm_button)
        view.add_item(cancel_button)
        
        embed = discord.Embed(
            title='⚠️ Economy Reset Confirmation',
            description='**WARNING:** This will permanently delete:\n• All user coins and bank balances\n• All user inventories\n\n**This action cannot be undone!**',
            color=0xFF0000,
            timestamp=datetime.utcnow()
        )
        
        await ctx.respond(embed=embed, view=view, ephemeral=True)


def setup(bot):
    bot.add_cog(Economy(bot))