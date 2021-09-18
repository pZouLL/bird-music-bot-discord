import asyncio
import youtube_dl
import pafy
import discord
from discord.ext import commands

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="-", intents=intents)

allowed_users = {
    'pzoull' : '287766415744958466',
    'jameslie' : '424397543729004544'
}


@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready.")
    await bot.change_presence(activity=discord.Game(name="-h For Help"))

class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot 
        self.song_queue = {}

        self.setup()

    def setup(self):
        for guild in self.bot.guilds:
            self.song_queue[guild.id] = []

    async def check_queue(self, ctx):
        if len(self.song_queue[ctx.guild.id]) > 0:
            ctx.voice_client.stop()
            await self.play_song(ctx, self.song_queue[ctx.guild.id][0])
            self.song_queue[ctx.guild.id].pop(0)

    async def search_song(self, amount, song, get_url=False):
        info = await self.bot.loop.run_in_executor(None, lambda: youtube_dl.YoutubeDL({"format" : "bestaudio", "quiet" : True}).extract_info(f"ytsearch{amount}:{song}", download=False, ie_key="YoutubeSearch"))
        if len(info["entries"]) == 0: return None

        return [entry["webpage_url"] for entry in info["entries"]] if get_url else info

    async def play_song(self, ctx, song):
        try:
            url = pafy.new(song).getbestaudio().url
            title = pafy.new(song).title
            embed = discord.Embed(colour=discord.Colour.dark_gold())
            embed.add_field(name = '***Now playing***' , value=f'{title}' , inline = False)
            await ctx.send(embed=embed)
            ctx.voice_client.play(await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS), after=lambda error: self.bot.loop.create_task(self.check_queue(ctx)))
            ctx.voice_client.source.volume = 0.5
        except KeyError:
            await ctx.send(embed=discord.Embed(title="Song Couldn't Be Played",color = discord.Colour.red())) 


    @commands.command()
    async def join(self, ctx):
        if str(ctx.message.author.id) in list(allowed_users.values()):
            if ctx.author.voice is None:
                return await ctx.send(embed=discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red()))

            if ctx.voice_client is not None:
                await ctx.voice_client.disconnect()

            await ctx.author.voice.channel.connect()
        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))

    @commands.command()
    async def cq(self,ctx):
        if str(ctx.message.author.id) in list(allowed_users.values()): 
            ctx.voice_client.stop()
            await ctx.send(embed=discord.Embed(title="Queue Cleared" , colour=discord.Colour.dark_gold()))
            for guild in self.bot.guilds:
                self.song_queue[guild.id] = []
            self.song_queue = {}
        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))  

    @commands.command()
    async def dc(self, ctx):
        if str(ctx.message.author.id) in list(allowed_users.values()): 
            if ctx.voice_client is not None:
                return await ctx.voice_client.disconnect()

            await ctx.send(embed=discord.Embed(title='Im Not Connected To A VC' , colour = discord.Colour.red()))
        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))

    @commands.command()
    async def p(self, ctx, *, song=None):
        if str(ctx.message.author.id) in list(allowed_users.values()): 
            if song is None:
                await ctx.send(embed=discord.Embed(title='Not Song Was Specified' , colour = discord.Colour.red()))

            if ctx.voice_client is None:
                await ctx.send(embed=discord.Embed(title='Use Join Command First' , colour = discord.Colour.red()))


            # handle song where song isn't url
            if not ("youtube.com/watch?" in song or "https://youtu.be/" in song):
                result = await self.search_song(1, song, get_url=True)

                if result is None:
                    embed = discord.Embed(title='Song Not Found' , color = discord.Color.red())
                    return await ctx.send(embed=embed)

                song = result[0]

                try:
                    video = pafy.new(song).title
                except:
                    return await ctx.send(embed=discord.Embed(title='Song Was Unavailable' , color = discord.Colour.red())) 

            if ctx.voice_client.is_playing():
                queue_len = len(self.song_queue[ctx.guild.id])

                if queue_len < 10:
                    self.song_queue[ctx.guild.id].append(song)
                    embed = discord.Embed(title='' , color = discord.Color.dark_gold())
                    embed.add_field(name="Song Added", value=f"Song Has Been Added To Queue {queue_len+1}", inline=False)
                    return await ctx.send(embed=embed)

                elif queue_len >= 10:
                    return await ctx.send(embed = discord.Embed(title='Only Up To 10 Queues' , color = discord.Color.red()))              
            await self.play_song(ctx, song)

        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))

    @commands.command() 
    async def search(self, ctx, *, song=None):
        if str(ctx.message.author.id) in list(allowed_users.values()): 
            if song is None: 
                embed = discord.Embed(title='No Song Was Specified' , colour=discord.Colour.red())
                return await ctx.send(embed = embed)

            info = await self.search_song(5, song)

            embed = discord.Embed(title=f"Results for '{song}':", description="*You can use these URL's to play an exact song if the one you want isn't the first result.*\n", colour=discord.Colour.dark_gold())
            
            amount = 0
            for entry in info["entries"]:
                embed.description += f"[{entry['title']}]({entry['webpage_url']})\n"
                amount += 1

            embed.set_footer(text=f"Displaying the first {amount} results.")
            await ctx.send(embed=embed)
        
        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))  

    @commands.command()
    async def dq(self,ctx,index):
        if str(ctx.message.author.id) in list(allowed_users.values()): 
            index = int(index)
            if len(self.song_queue[ctx.guild.id])+1 < index or index <= 0:
                embed = discord.Embed(title='Invalid Number!' , colour=discord.Colour.red())
                return await ctx.send(embed = embed)
            else:
                index -= 1 
                self.song_queue[ctx.guild.id].pop(index)
                embed = discord.Embed(title=f"Queue {index+1} Remove" , colour=discord.Colour.dark_gold())
                await ctx.send(embed=embed)

        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))  




    @commands.command()
    async def q(self, ctx): # display the current guilds queue
        if str(ctx.message.author.id) in list(allowed_users.values()): 
            if len(self.song_queue[ctx.guild.id]) == 0:
                embed = discord.Embed(title='No Song In Queue' , colour=discord.Colour.dark_gold())
                return await ctx.send(embed=embed)

            embed = discord.Embed(title="Song Queue", description="", colour=discord.Colour.dark_gold())
            i = 1
            for url in self.song_queue[ctx.guild.id]:
                video = pafy.new(url).title 
                embed.description += f"{i}) {video}\n"

                i += 1

            await ctx.send(embed=embed)

        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))  

    @commands.command()
    async def h(self,ctx):
        await ctx.send("""
```
List Of Commands:
-p = Play Song
-search = Search Song
-s = Skip
-q = See Queue
-pause = Pause
-resume = Resume
-join = Join
-cq = Clear Queue 
-dq [number] = Delete Queue
-h = Help
```
        """)

    @commands.command()
    async def s(self, ctx):
        if str(ctx.message.author.id) in list(allowed_users.values()):
            if ctx.voice_client is None:
                embed = discord.Embed(title='Currently Not Playing Any Song' , colour=discord.Colour.red())
                return await ctx.send(embed=embed)

            if ctx.author.voice is None:
                embed = discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red())
                return await ctx.send(embed=embed)

            if ctx.author.voice.channel.id != ctx.voice_client.channel.id:
                embed = discord.Embed(title='Please Join The Same VC' , colour=discord.Colour.red())
                return await ctx.send(embed=embed)


            await ctx.send(embed = discord.Embed(title='Skip Succesfull' , colour=discord.Colour.dark_gold()))


            ctx.voice_client.stop()
            await self.check_queue(ctx)

        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))  

    @commands.command()
    async def pause(self, ctx):
        if str(ctx.message.author.id) in list(allowed_users.values()):
            if ctx.voice_client.is_paused():
                return await ctx.send(embed = discord.Embed(title='Already Paused' , colour=discord.Colour.red()))

            ctx.voice_client.pause()
            await ctx.send(embed = discord.Embed("***Pause Succesfull***" , colour=discord.Colour.dark_gold()))
        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))  


    @commands.command()
    async def resume(self, ctx):
        if str(ctx.message.author.id) in list(allowed_users.values()):
            if ctx.voice_client is None:
                return await ctx.send(embed = discord.Embed(title='Connect Me To A VC' , colour=discord.Colour.red()))

            if not ctx.voice_client.is_paused():
                return await ctx.send(embed = discord.Embed(title='Already Playing Song' , colour=discord.Colour.red()))
            
            ctx.voice_client.resume()
        else:
            return await ctx.send(embed=discord.Embed(title="You Don't Have The Necessary Permissions" , colour=discord.Colour.red()))     
        
async def setup():
    await bot.wait_until_ready()
    bot.add_cog(Player(bot))

bot.loop.create_task(setup())

bot.run('ODg3NTcxNTE1OTQ2NzA0OTI2.YUGFYw.8VUELMaV2Lzy0M1MsCc1RLpZ4w4')
