import discord
from discord.ext import commands
from discord import option
from datetime import datetime
from typing import Optional
import random
import logging
from utils.database import bot_data
from utils.config import Config, GAMBLE_GAMES

logger = logging.getLogger('tooly_bot.gambling')

class Gambling(commands.Cog):
    """Gambling system with 4 different games"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @discord.slash_command(name='gamble', description='Play various gambling games (max 50% of wallet)')
    @option("game", description="Game type", choices=["slots", "dice", "coinflip", "roulette"])
    @option("amount", description="Amount to gamble", min_value=Config.GAMBLE_MIN)
    async def gamble(self, ctx, game: str, amount: int):
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        
        max_bet = int(economy_data['coins'] * Config.GAMBLE_MAX_PERCENT)
        if amount > max_bet:
            await ctx.respond(
                f'❌ You can only gamble up to 50% of your wallet (**{max_bet:,} coins**)!',
                ephemeral=True
            )
            return
        
        if amount > economy_data['coins']:
            await ctx.respond('❌ You don\'t have enough coins!', ephemeral=True)
            return
        
        if game == 'slots':
            result = self.play_slots(amount)
        elif game == 'dice':
            result = self.play_dice(amount)
        elif game == 'coinflip':
            result = self.play_coinflip(amount)
        elif game == 'roulette':
            result = self.play_roulette(amount)
        
        if result['won']:
            economy_data['coins'] += result['winnings']
            economy_data['gamblingWins'] = economy_data.get('gamblingWins', 0) + 1
            economy_data['currentStreak'] = economy_data.get('currentStreak', 0) + 1
            
            if economy_data['currentStreak'] > economy_data.get('winStreak', 0):
                economy_data['winStreak'] = economy_data['currentStreak']
            
            if result['winnings'] > economy_data.get('biggestWin', 0):
                economy_data['biggestWin'] = result['winnings']
        else:
            economy_data['coins'] -= amount
            economy_data['gamblingLosses'] = economy_data.get('gamblingLosses', 0) + 1
            economy_data['currentStreak'] = 0
            
            if amount > economy_data.get('biggestLoss', 0):
                economy_data['biggestLoss'] = amount
        
        economy_data['totalGambled'] = economy_data.get('totalGambled', 0) + amount
        bot_data.set_user_economy(guild_id, user_id, economy_data)
        bot_data.save()
        
        embed = result['embed']
        embed.set_footer(text=f'⚠️ Gamble responsibly! Win Streak: {economy_data["currentStreak"]}')
        
        await ctx.respond(embed=embed)
    
    @discord.slash_command(name='gamblestats', description='View your gambling statistics')
    @option("user", discord.Member, description="User to check (optional)", required=False)
    async def gamblestats(self, ctx, user: Optional[discord.Member] = None):
        guild_id = str(ctx.guild.id)
        target = user or ctx.author
        user_id = str(target.id)
        economy_data = bot_data.get_user_economy(guild_id, user_id)
        
        total_games = economy_data.get('gamblingWins', 0) + economy_data.get('gamblingLosses', 0)
        
        if total_games == 0:
            await ctx.respond(f'❌ {target.display_name} hasn\'t gambled yet!')
            return
        
        win_rate = (economy_data.get('gamblingWins', 0) / total_games) * 100
        
        embed = discord.Embed(
            title=f'🎰 {target.display_name}\'s Gambling Stats',
            color=0xFF69B4,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        embed.add_field(name='🎮 Total Games', value=f'{total_games:,}', inline=True)
        embed.add_field(name='✅ Wins', value=f'{economy_data.get("gamblingWins", 0):,}', inline=True)
        embed.add_field(name='❌ Losses', value=f'{economy_data.get("gamblingLosses", 0):,}', inline=True)
        
        embed.add_field(name='📊 Win Rate', value=f'{win_rate:.1f}%', inline=True)
        embed.add_field(name='🔥 Best Streak', value=f'{economy_data.get("winStreak", 0):,}', inline=True)
        embed.add_field(name='⚡ Current Streak', value=f'{economy_data.get("currentStreak", 0):,}', inline=True)
        
        embed.add_field(name='💰 Total Gambled', value=f'{economy_data.get("totalGambled", 0):,} coins', inline=True)
        embed.add_field(name='🏆 Biggest Win', value=f'{economy_data.get("biggestWin", 0):,} coins', inline=True)
        embed.add_field(name='💔 Biggest Loss', value=f'{economy_data.get("biggestLoss", 0):,} coins', inline=True)
        
        await ctx.respond(embed=embed)
    
    def play_slots(self, bet: int) -> dict:
        game = GAMBLE_GAMES['slots']
        symbols = game['symbols']
        result = [random.choice(symbols) for _ in range(3)]
        
        if result[0] == result[1] == result[2]:
            multiplier = game['payouts'][3]
            winnings = int(bet * multiplier)
            
            embed = discord.Embed(
                title='🎰 JACKPOT! 🎰',
                description=f'{result[0]} {result[1]} {result[2]}\n\n**THREE OF A KIND!**',
                color=0xFFD700,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Bet', value=f'{bet:,} coins', inline=True)
            embed.add_field(name='Won', value=f'{winnings:,} coins', inline=True)
            embed.add_field(name='Multiplier', value=f'{multiplier}x', inline=True)
            
            return {'won': True, 'winnings': winnings, 'embed': embed}
        
        elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
            multiplier = game['payouts'][2]
            winnings = int(bet * multiplier)
            
            embed = discord.Embed(
                title='🎰 Winner!',
                description=f'{result[0]} {result[1]} {result[2]}\n\n**TWO OF A KIND!**',
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Bet', value=f'{bet:,} coins', inline=True)
            embed.add_field(name='Won', value=f'{winnings:,} coins', inline=True)
            embed.add_field(name='Multiplier', value=f'{multiplier}x', inline=True)
            
            return {'won': True, 'winnings': winnings, 'embed': embed}
        
        else:
            embed = discord.Embed(
                title='🎰 No Match',
                description=f'{result[0]} {result[1]} {result[2]}\n\nBetter luck next time!',
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Lost', value=f'{bet:,} coins', inline=True)
            
            return {'won': False, 'winnings': 0, 'embed': embed}
    
    def play_dice(self, bet: int) -> dict:
        game = GAMBLE_GAMES['dice']
        player_roll = random.randint(1, 6)
        house_roll = random.randint(1, 6)
        
        if player_roll > house_roll:
            multiplier = random.uniform(*game['multiplier_range'])
            winnings = int(bet * multiplier)
            
            embed = discord.Embed(
                title='🎲 Dice Roll - YOU WIN!',
                description=f'Your Roll: **{player_roll}** 🎲\nHouse Roll: **{house_roll}** 🎲',
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Bet', value=f'{bet:,} coins', inline=True)
            embed.add_field(name='Won', value=f'{winnings:,} coins', inline=True)
            embed.add_field(name='Multiplier', value=f'{multiplier:.2f}x', inline=True)
            
            return {'won': True, 'winnings': winnings, 'embed': embed}
        
        elif player_roll == house_roll:
            embed = discord.Embed(
                title='🎲 Dice Roll - TIE!',
                description=f'Your Roll: **{player_roll}** 🎲\nHouse Roll: **{house_roll}** 🎲\n\nYour bet is returned!',
                color=0xFFA500,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Bet Returned', value=f'{bet:,} coins', inline=True)
            
            return {'won': True, 'winnings': 0, 'embed': embed}
        
        else:
            embed = discord.Embed(
                title='🎲 Dice Roll - YOU LOSE',
                description=f'Your Roll: **{player_roll}** 🎲\nHouse Roll: **{house_roll}** 🎲',
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Lost', value=f'{bet:,} coins', inline=True)
            
            return {'won': False, 'winnings': 0, 'embed': embed}
    
    def play_coinflip(self, bet: int) -> dict:
        game = GAMBLE_GAMES['coinflip']
        player_choice = random.choice(['Heads', 'Tails'])
        result = random.choice(['Heads', 'Tails'])
        
        if player_choice == result:
            winnings = int(bet * game['multiplier'])
            
            embed = discord.Embed(
                title='🪙 Coin Flip - YOU WIN!',
                description=f'You chose: **{player_choice}**\nResult: **{result}**',
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Bet', value=f'{bet:,} coins', inline=True)
            embed.add_field(name='Won', value=f'{winnings:,} coins', inline=True)
            embed.add_field(name='Multiplier', value=f'{game["multiplier"]}x', inline=True)
            
            return {'won': True, 'winnings': winnings, 'embed': embed}
        
        else:
            embed = discord.Embed(
                title='🪙 Coin Flip - YOU LOSE',
                description=f'You chose: **{player_choice}**\nResult: **{result}**',
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Lost', value=f'{bet:,} coins', inline=True)
            
            return {'won': False, 'winnings': 0, 'embed': embed}
    
    def play_roulette(self, bet: int) -> dict:
        game = GAMBLE_GAMES['roulette']
        colors = game['colors']
        player_choice = random.choice(colors)
        result = random.choice(colors)
        
        if result == '🟢':
            winnings = int(bet * game['payouts']['green'])
            
            embed = discord.Embed(
                title='🎡 Roulette - JACKPOT! 🎡',
                description=f'Result: **GREEN** 🟢\n\n**MEGA WIN!**',
                color=0xFFD700,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Bet', value=f'{bet:,} coins', inline=True)
            embed.add_field(name='Won', value=f'{winnings:,} coins', inline=True)
            embed.add_field(name='Multiplier', value=f'{game["payouts"]["green"]}x', inline=True)
            
            return {'won': True, 'winnings': winnings, 'embed': embed}
        
        elif player_choice == result:
            winnings = int(bet * game['payouts']['color'])
            
            embed = discord.Embed(
                title='🎡 Roulette - YOU WIN!',
                description=f'You chose: {player_choice}\nResult: {result}',
                color=0x00FF00,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Bet', value=f'{bet:,} coins', inline=True)
            embed.add_field(name='Won', value=f'{winnings:,} coins', inline=True)
            embed.add_field(name='Multiplier', value=f'{game["payouts"]["color"]}x', inline=True)
            
            return {'won': True, 'winnings': winnings, 'embed': embed}
        
        else:
            embed = discord.Embed(
                title='🎡 Roulette - YOU LOSE',
                description=f'You chose: {player_choice}\nResult: {result}',
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            embed.add_field(name='Lost', value=f'{bet:,} coins', inline=True)
            
            return {'won': False, 'winnings': 0, 'embed': embed}

def setup(bot):
    bot.add_cog(Gambling(bot))