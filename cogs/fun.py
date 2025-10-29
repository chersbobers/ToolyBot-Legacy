import discord
from discord.ext import commands
from discord import option
from datetime import datetime
import random
import aiohttp
import logging

logger = logging.getLogger('tooly_bot.fun')

class Fun(commands.Cog):
    """Fun commands like animals, jokes, and games"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @discord.slash_command(name='flip', description='Flip a coin')
    async def flip(self, ctx):
        result = random.choice(['Heads', 'Tails'])
        await ctx.respond(f'🪙 The coin landed on **{result}**!')
    
    @discord.slash_command(name='8ball', description='Ask the magic 8-ball a question')
    @option("question", description="Your question for the 8-ball")
    async def eightball(self, ctx, question: str):
        responses = [
            'Yes, definitely!', 'No way!', 'Maybe...', 'Ask again later', 
            'Absolutely!', 'I doubt it', 'Signs point to yes', 'Very doubtful', 
            'Without a doubt', 'My sources say no', 'Outlook good', 'Cannot predict now'
        ]
        await ctx.respond(f'🎱 **{question[:200]}**\n{random.choice(responses)}')
    
    @discord.slash_command(name='roll', description='Roll a dice (1-6)')
    async def roll(self, ctx):
        result = random.randint(1, 6)
        await ctx.respond(f'🎲 You rolled a **{result}**!')
    
    @discord.slash_command(name='hello', description='Say hello to the bot')
    async def hello(self, ctx):
        await ctx.respond(f'Hello {ctx.author.mention}! 👋 I\'m Tooly Bot!')
    
    @discord.slash_command(name='kitty', description='Get a random cat picture')
    async def kitty(self, ctx):
        await ctx.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.thecatapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    embed = discord.Embed(
                        title='🐱 Random Kitty!', 
                        color=0xFF69B4, 
                        timestamp=datetime.utcnow()
                    )
                    embed.set_image(url=data[0]['url'])
                    embed.set_footer(text=f'Requested by {ctx.author.name}')
                    await ctx.followup.send(embed=embed)
        except Exception as e:
            logger.error(f'Cat API error: {e}')
            await ctx.followup.send('Failed to fetch a cat picture 😿')
    
    @discord.slash_command(name='doggy', description='Get a random dog picture')
    async def doggy(self, ctx):
        await ctx.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.thedogapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    embed = discord.Embed(
                        title='🐶 Random Doggy!', 
                        color=0xFF69B4, 
                        timestamp=datetime.utcnow()
                    )
                    embed.set_image(url=data[0]['url'])
                    embed.set_footer(text=f'Requested by {ctx.author.name}')
                    await ctx.followup.send(embed=embed)
        except Exception as e:
            logger.error(f'Dog API error: {e}')
            await ctx.followup.send('Failed to fetch a dog picture 😥')
    
    @discord.slash_command(name='randompet', description='Get a random pet picture (cat or dog)')
    async def random_pet(self, ctx):
        await ctx.defer()
        pet_num = random.randint(1, 2)
        try:
            async with aiohttp.ClientSession() as session:
                if pet_num == 1:
                    async with session.get('https://api.thecatapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        data = await resp.json()
                        title = 'Random Pet! 🐱'
                else:
                    async with session.get('https://api.thedogapi.com/v1/images/search', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        data = await resp.json()
                        title = 'Random Pet! 🐶'
                
                embed = discord.Embed(title=title, color=0xFF69B4, timestamp=datetime.utcnow())
                embed.set_image(url=data[0]['url'])
                embed.set_footer(text=f'Requested by {ctx.author.name}')
                await ctx.followup.send(embed=embed)
        except Exception as e:
            logger.error(f'Pet API error: {e}')
            await ctx.followup.send('Failed to fetch a pet picture 😥')
    
    @discord.slash_command(name='joke', description='Get a random joke')
    async def joke(self, ctx):
        await ctx.defer()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://official-joke-api.appspot.com/random_joke', timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    data = await resp.json()
                    embed = discord.Embed(
                        title='😂 Random Joke', 
                        description=f'**{data["setup"]}**\n\n||{data["punchline"]}||', 
                        color=0xFFA500, 
                        timestamp=datetime.utcnow()
                    )
                    embed.set_footer(text=f'{data["type"]} joke')
                    await ctx.followup.send(embed=embed)
        except:
            jokes = [
                {'setup': 'Why did the scarecrow win an award?', 'punchline': 'Because he was outstanding in his field!'},
                {'setup': 'Why don\'t scientists trust atoms?', 'punchline': 'Because they make up everything!'},
                {'setup': 'What do you call a fake noodle?', 'punchline': 'An impasta!'},
                {'setup': 'Why did the bicycle fall over?', 'punchline': 'Because it was two tired!'},
            ]
            j = random.choice(jokes)
            embed = discord.Embed(
                title='😂 Random Joke', 
                description=f'**{j["setup"]}**\n\n||{j["punchline"]}||', 
                color=0xFFA500, 
                timestamp=datetime.utcnow()
            )
            await ctx.followup.send(embed=embed)
    
    @discord.slash_command(name='yotsuba', description='Get a Yotsuba image')
    async def yotsuba(self, ctx):
        embed = discord.Embed(
            title='🍀 Yotsuba!',
            description='Here\'s a Yotsuba image!',
            color=0x77DD77,
            timestamp=datetime.utcnow()
        )
        embed.set_image(url='https://i.ibb.co/BDhQV8B/yotsuba.jpg')
        await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Fun(bot))
