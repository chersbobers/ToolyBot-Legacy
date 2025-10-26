import discord
from discord.ext import commands
from discord import option
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        if isinstance(message.channel, discord.DMChannel):
            try:
                embed = discord.Embed(
                    title="📬 DM Received",
                    description=message.content,
                    color=0x2ECC71,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
                embed.set_footer(text=f"User ID: {message.author.id}")
                
                for guild in self.bot.guilds:
                    target_channel = discord.utils.get(guild.text_channels, name="mod-mail") or \
                                   discord.utils.get(guild.text_channels, name="staff") or \
                                   discord.utils.get(guild.text_channels, name="admin") or \
                                   guild.system_channel or \
                                   guild.text_channels[0] if guild.text_channels else None
                    
                    if target_channel:
                        await target_channel.send(embed=embed)
                        logger.info(f"DM from {message.author} forwarded to {guild.name}")
                
                await message.reply("✅ Your message has been sent to the server staff. They will respond soon!")
                
            except Exception as e:
                logger.error(f"Error handling DM from {message.author}: {e}", exc_info=True)
                try:
                    await message.reply("⚠️ There was an error forwarding your message. Please try again later.")
                except:
                    pass

    @discord.slash_command(name='mute', description='Mute a member (Admin only)')
    @option("user", discord.Member, description="Member to mute")
    @option("reason", description="Reason for mute", required=False)
    @discord.default_permissions(administrator=True)
    async def mute(self, ctx, user: discord.Member, reason: str = "No reason provided"):
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                await channel.set_permissions(role, send_messages=False, speak=False)

        await user.add_roles(role, reason=reason)
        await ctx.respond(f"🔇 {user.mention} has been muted. Reason: {reason}")

    @discord.slash_command(name='unmute', description='Unmute a member (Admin only)')
    @option("user", discord.Member, description="Member to unmute")
    @discord.default_permissions(administrator=True)
    async def unmute(self, ctx, user: discord.Member):
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if role in user.roles:
            await user.remove_roles(role)
            await ctx.respond(f"🔊 {user.mention} has been unmuted.")
        else:
            await ctx.respond("❌ That user is not muted.")

    @discord.slash_command(name='kick', description='Kick a member (Admin only)')
    @option("user", discord.Member, description="Member to kick")
    @option("reason", description="Reason for kick", required=False)
    @discord.default_permissions(administrator=True)
    async def kick(self, ctx, user: discord.Member, reason: str = "No reason provided"):
        await user.kick(reason=reason)
        await ctx.respond(f"👢 {user.mention} has been kicked. Reason: {reason}")

    @discord.slash_command(name='ban', description='Ban a member (Admin only)')
    @option("user", discord.Member, description="Member to ban")
    @option("reason", description="Reason for ban", required=False)
    @discord.default_permissions(administrator=True)
    async def ban(self, ctx, user: discord.Member, reason: str = "No reason provided"):
        await user.ban(reason=reason)
        await ctx.respond(f"🔨 {user.mention} has been banned. Reason: {reason}")

    @discord.slash_command(name='unban', description='Unban a member (Admin only)')
    @option("username", description="Username#1234 of the user to unban")
    @discord.default_permissions(administrator=True)
    async def unban(self, ctx, username: str):
        banned_users = await ctx.guild.bans()
        name, discriminator = username.split('#')

        for ban_entry in banned_users:
            user = ban_entry.user
            if (user.name, user.discriminator) == (name, discriminator):
                await ctx.guild.unban(user)
                await ctx.respond(f"✅ Unbanned {user.mention}")
                return

        await ctx.respond("❌ User not found in ban list.")

    @discord.slash_command(name='dm', description='Send a direct message to a user (Admin only)')
    @option("user", discord.Member, description="User to DM")
    @option("message", description="Message to send")
    @discord.default_permissions(administrator=True)
    async def dm(self, ctx, user: discord.Member, message: str):
        await ctx.defer(ephemeral=True)
        try:
            embed = discord.Embed(
                title="📨 Message from Server Staff",
                description=message,
                color=0x3498DB,
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text=f"Sent by {ctx.author.display_name} from {ctx.guild.name}")

            await user.send(embed=embed)
            await ctx.followup.send(f"✅ Message sent to {user.mention}", ephemeral=True)
            logger.info(f"DM sent to {user} by {ctx.author} in {ctx.guild.name}")

        except discord.Forbidden:
            await ctx.followup.send(f"❌ {user.mention} has DMs disabled or blocked the bot.", ephemeral=True)
            logger.warning(f"Could not DM {user} - DMs disabled or bot blocked")
        except Exception as e:
            await ctx.followup.send(f"⚠️ Error sending message: {str(e)}", ephemeral=True)
            logger.error(f"Error sending DM to {user}: {e}", exc_info=True)


def setup(bot):
    bot.add_cog(Moderation(bot))