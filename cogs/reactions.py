import discord
from discord.ext import commands
from discord import option
import logging
from utils.database import bot_data, reaction_roles

logger = logging.getLogger('tooly_bot.reactions')


class Reactions(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        guild_id = str(payload.guild_id)
        emoji_str = str(payload.emoji)
        role_id = reaction_roles.get_role_for_reaction(guild_id, str(payload.message_id), emoji_str)

        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role = guild.get_role(int(role_id))
        if not role:
            logger.warning(f'Role {role_id} not found')
            return

        member = guild.get_member(payload.user_id)
        if not member:
            return

        try:
            await member.add_roles(role)
            logger.info(f'✅ Added role {role.name} to {member.name}')
        except discord.Forbidden:
            logger.error(f'❌ Missing permissions to add role {role.name}')
        except Exception as e:
            logger.error(f'❌ Error adding role: {e}')

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        guild_id = str(payload.guild_id)
        emoji_str = str(payload.emoji)
        role_id = reaction_roles.get_role_for_reaction(guild_id, str(payload.message_id), emoji_str)

        if not role_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        role = guild.get_role(int(role_id))
        if not role:
            return

        member = guild.get_member(payload.user_id)
        if not member:
            return

        try:
            await member.remove_roles(role)
            logger.info(f'➖ Removed role {role.name} from {member.name}')
        except discord.Forbidden:
            logger.error(f'❌ Missing permissions to remove role {role.name}')
        except Exception as e:
            logger.error(f'❌ Error removing role: {e}')

    @discord.slash_command(name='reactionrole', description='[ADMIN] Create a reaction role')
    @option("message_id", description="Message ID to add reactions to")
    @option("emoji", description="Emoji to use (e.g., 🎮 or :custom_emoji:)")
    @option("role", discord.Role, description="Role to assign")
    @discord.default_permissions(administrator=True)
    async def reactionrole(self, ctx, message_id: str, emoji: str, role: discord.Role):
        guild_id = str(ctx.guild.id)

        try:
            message = await ctx.channel.fetch_message(int(message_id))
        except discord.NotFound:
            await ctx.respond('❌ Message not found in this channel!', ephemeral=True)
            return
        except ValueError:
            await ctx.respond('❌ Invalid message ID!', ephemeral=True)
            return

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await ctx.respond('❌ Invalid emoji or unable to add reaction!', ephemeral=True)
            return

        reaction_roles.add_reaction_role(guild_id, message_id, emoji, str(role.id))

        embed = discord.Embed(
            title='✅ Reaction Role Created',
            description=f'React with {emoji} on the message to get {role.mention}',
            color=0x00FF00
        )
        embed.add_field(name='Message ID', value=message_id, inline=True)
        embed.add_field(name='Emoji', value=emoji, inline=True)
        embed.add_field(name='Role', value=role.mention, inline=True)

        await ctx.respond(embed=embed)
        logger.info(f'✅ Created reaction role: {emoji} -> {role.name}')

    @discord.slash_command(name='removereactionrole', description='[ADMIN] Remove a reaction role')
    @option("message_id", description="Message ID")
    @option("emoji", description="Emoji to remove (optional - removes all if not specified)", required=False)
    @discord.default_permissions(administrator=True)
    async def removereactionrole(self, ctx, message_id: str, emoji: str = None):
        guild_id = str(ctx.guild.id)

        if guild_id not in reaction_roles.data or message_id not in reaction_roles.data.get(guild_id, {}):
            await ctx.respond('❌ No reaction roles found for that message!', ephemeral=True)
            return

        if emoji:
            if emoji not in reaction_roles.data[guild_id][message_id]:
                await ctx.respond('❌ That emoji is not set up for reaction roles!', ephemeral=True)
                return

            reaction_roles.remove_reaction_role(guild_id, message_id, emoji)
            await ctx.respond(f'✅ Removed reaction role for {emoji}')
        else:
            reaction_roles.remove_reaction_role(guild_id, message_id)
            await ctx.respond(f'✅ Removed all reaction roles from message {message_id}')

    @discord.slash_command(name='listreactionroles', description='List all reaction roles')
    async def listreactionroles(self, ctx):
        guild_id = str(ctx.guild.id)
        guild_reactions = reaction_roles.data.get(guild_id, {})

        if not guild_reactions:
            await ctx.respond('No reaction roles configured yet!')
            return

        embed = discord.Embed(
            title='🎭 Reaction Roles',
            color=0x9B59B6
        )

        for message_id, reactions in guild_reactions.items():
            roles_text = []
            for emoji, role_id in reactions.items():
                role = ctx.guild.get_role(int(role_id))
                role_name = role.mention if role else f'Role ID: {role_id}'
                roles_text.append(f'{emoji} → {role_name}')

            embed.add_field(
                name=f'Message ID: {message_id}',
                value='\n'.join(roles_text) if roles_text else 'No reactions',
                inline=False
            )

        await ctx.respond(embed=embed)

    @discord.slash_command(name='createreactionpanel', description='[ADMIN] Create a reaction role panel')
    @option("title", description="Panel title")
    @option("description", description="Panel description")
    @discord.default_permissions(administrator=True)
    async def createreactionpanel(self, ctx, title: str, description: str):
        embed = discord.Embed(
            title=f'🎭 {title}',
            description=description,
            color=0x9B59B6
        )
        embed.set_footer(text='React below to get your roles!')

        message = await ctx.channel.send(embed=embed)

        await ctx.respond(
            f'✅ Panel created! Message ID: `{message.id}`\n'
            f'Use `/reactionrole {message.id} <emoji> <role>` to add roles to it.',
            ephemeral=True
        )


def setup(bot):
    bot.add_cog(Reactions(bot))
