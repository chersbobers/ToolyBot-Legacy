import discord
from discord.ext import commands
from discord import option
from datetime import datetime, timezone
import logging
import json
import os

logger = logging.getLogger(__name__)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.timeout_file = "timeout_roles.json"
        self._ensure_timeout_file()

    def _ensure_timeout_file(self):
        """Create the timeout roles file if it doesn't exist"""
        if not os.path.exists(self.timeout_file):
            with open(self.timeout_file, 'w') as f:
                json.dump({}, f)

    def _load_timeout_data(self):
        """Load timeout data from file"""
        try:
            with open(self.timeout_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading timeout data: {e}")
            return {}

    def _save_timeout_data(self, data):
        """Save timeout data to file"""
        try:
            with open(self.timeout_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving timeout data: {e}")

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

    @discord.slash_command(name='timeout', description='Timeout a member by removing their roles (Admin only)')
    @option("user", discord.Member, description="Member to timeout")
    @option("reason", description="Reason for timeout", required=False)
    @discord.default_permissions(administrator=True)
    async def timeout(self, ctx, user: discord.Member, reason: str = "No reason provided"):
        await ctx.defer()
        
        try:
            # Check if user is already timed out
            timeout_data = self._load_timeout_data()
            user_key = f"{ctx.guild.id}_{user.id}"
            
            if user_key in timeout_data:
                await ctx.followup.send(f"❌ {user.mention} is already timed out.")
                return

            # Get or create the Timeout role
            timeout_role = discord.utils.get(ctx.guild.roles, name="Timeout")
            if not timeout_role:
                timeout_role = await ctx.guild.create_role(
                    name="Timeout",
                    color=discord.Color.orange(),
                    reason="Timeout role created by moderation system"
                )
                logger.info(f"Created Timeout role in {ctx.guild.name}")

            # Save user's current roles (excluding @everyone and managed roles)
            saved_roles = []
            roles_to_remove = []
            
            for role in user.roles:
                if role.name != "@everyone" and not role.managed and role.id != timeout_role.id:
                    saved_roles.append(role.id)
                    roles_to_remove.append(role)

            # Save to file
            timeout_data[user_key] = {
                "user_id": user.id,
                "guild_id": ctx.guild.id,
                "roles": saved_roles,
                "reason": reason,
                "timed_out_by": ctx.author.id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self._save_timeout_data(timeout_data)

            # Remove roles and add timeout role
            try:
                await user.remove_roles(*roles_to_remove, reason=f"Timeout by {ctx.author}: {reason}")
                await user.add_roles(timeout_role, reason=f"Timeout by {ctx.author}: {reason}")
                
                embed = discord.Embed(
                    title="⏸️ User Timed Out",
                    description=f"{user.mention} has been placed in timeout.",
                    color=0xFF8C00,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
                embed.add_field(name="Roles Saved", value=str(len(saved_roles)), inline=True)
                embed.set_footer(text=f"User ID: {user.id}")
                
                await ctx.followup.send(embed=embed)
                logger.info(f"{user} timed out by {ctx.author} in {ctx.guild.name}. {len(saved_roles)} roles saved.")
                
                # Try to notify the user
                try:
                    dm_embed = discord.Embed(
                        title="⏸️ You've Been Timed Out",
                        description=f"You have been placed in timeout in **{ctx.guild.name}**.",
                        color=0xFF8C00,
                        timestamp=datetime.now(timezone.utc)
                    )
                    dm_embed.add_field(name="Reason", value=reason, inline=False)
                    dm_embed.add_field(name="What this means", value="Your roles have been temporarily removed. You can access timeout forums. Contact staff if you have questions.", inline=False)
                    await user.send(embed=dm_embed)
                except:
                    pass  # User has DMs disabled
                
            except discord.Forbidden:
                await ctx.followup.send(f"❌ I don't have permission to modify {user.mention}'s roles.")
                # Remove from timeout data since we couldn't complete the action
                del timeout_data[user_key]
                self._save_timeout_data(timeout_data)
                
        except Exception as e:
            await ctx.followup.send(f"⚠️ An error occurred: {str(e)}")
            logger.error(f"Error timing out {user}: {e}", exc_info=True)

    @discord.slash_command(name='untimeout', description='Remove timeout and restore roles (Admin only)')
    @option("user", discord.Member, description="Member to untimeout")
    @discord.default_permissions(administrator=True)
    async def untimeout(self, ctx, user: discord.Member):
        await ctx.defer()
        
        try:
            timeout_data = self._load_timeout_data()
            user_key = f"{ctx.guild.id}_{user.id}"
            
            if user_key not in timeout_data:
                await ctx.followup.send(f"❌ {user.mention} is not currently timed out.")
                return

            user_data = timeout_data[user_key]
            saved_role_ids = user_data.get("roles", [])
            
            # Get the timeout role
            timeout_role = discord.utils.get(ctx.guild.roles, name="Timeout")
            
            # Get the role objects
            roles_to_restore = []
            missing_roles = []
            
            for role_id in saved_role_ids:
                role = ctx.guild.get_role(role_id)
                if role:
                    roles_to_restore.append(role)
                else:
                    missing_roles.append(role_id)

            # Restore roles and remove timeout role
            try:
                if timeout_role and timeout_role in user.roles:
                    await user.remove_roles(timeout_role, reason=f"Untimeout by {ctx.author}")
                
                if roles_to_restore:
                    await user.add_roles(*roles_to_restore, reason=f"Untimeout by {ctx.author}")
                
                # Remove from timeout data
                del timeout_data[user_key]
                self._save_timeout_data(timeout_data)
                
                embed = discord.Embed(
                    title="▶️ User Untimeout",
                    description=f"{user.mention} has been removed from timeout.",
                    color=0x2ECC71,
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
                embed.add_field(name="Roles Restored", value=str(len(roles_to_restore)), inline=True)
                
                if missing_roles:
                    embed.add_field(name="⚠️ Missing Roles", value=f"{len(missing_roles)} role(s) no longer exist and couldn't be restored.", inline=False)
                
                embed.set_footer(text=f"User ID: {user.id}")
                
                await ctx.followup.send(embed=embed)
                logger.info(f"{user} untimed out by {ctx.author} in {ctx.guild.name}. {len(roles_to_restore)} roles restored.")
                
                # Try to notify the user
                try:
                    dm_embed = discord.Embed(
                        title="▶️ Timeout Removed",
                        description=f"Your timeout in **{ctx.guild.name}** has been removed and your roles have been restored.",
                        color=0x2ECC71,
                        timestamp=datetime.now(timezone.utc)
                    )
                    await user.send(embed=dm_embed)
                except:
                    pass  # User has DMs disabled
                
            except discord.Forbidden:
                await ctx.followup.send(f"❌ I don't have permission to modify {user.mention}'s roles.")
                
        except Exception as e:
            await ctx.followup.send(f"⚠️ An error occurred: {str(e)}")
            logger.error(f"Error untiming out {user}: {e}", exc_info=True)

    @discord.slash_command(name='timeouts', description='View all active timeouts (Admin only)')
    @discord.default_permissions(administrator=True)
    async def timeouts(self, ctx):
        await ctx.defer()
        
        try:
            timeout_data = self._load_timeout_data()
            guild_timeouts = [data for key, data in timeout_data.items() if data.get("guild_id") == ctx.guild.id]
            
            if not guild_timeouts:
                await ctx.followup.send("✅ No users are currently timed out.")
                return

            embed = discord.Embed(
                title="⏸️ Active Timeouts",
                description=f"Total: {len(guild_timeouts)} user(s)",
                color=0xFF8C00,
                timestamp=datetime.now(timezone.utc)
            )
            
            for data in guild_timeouts[:10]:  # Limit to 10 to avoid embed limits
                user = ctx.guild.get_member(data["user_id"])
                user_name = user.mention if user else f"<@{data['user_id']}>"
                
                moderator = ctx.guild.get_member(data.get("timed_out_by", 0))
                mod_name = moderator.mention if moderator else "Unknown"
                
                timestamp = data.get("timestamp", "Unknown")
                reason = data.get("reason", "No reason provided")
                roles_count = len(data.get("roles", []))
                
                embed.add_field(
                    name=f"{user_name}",
                    value=f"**Reason:** {reason}\n**By:** {mod_name}\n**Roles Saved:** {roles_count}\n**Date:** <t:{int(datetime.fromisoformat(timestamp).timestamp())}:R>",
                    inline=False
                )
            
            if len(guild_timeouts) > 10:
                embed.set_footer(text=f"Showing 10 of {len(guild_timeouts)} timeouts")
            
            await ctx.followup.send(embed=embed)
            
        except Exception as e:
            await ctx.followup.send(f"⚠️ An error occurred: {str(e)}")
            logger.error(f"Error viewing timeouts: {e}", exc_info=True)

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