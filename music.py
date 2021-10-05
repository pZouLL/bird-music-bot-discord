from discord.errors import ClientException
import youtube_dl
import pafy
import discord
from discord.ext import commands
from discord.utils import get
import os 
from keepalive import keep_alive

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command('help')


@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready.")
    await bot.change_presence(activity=discord.Game(name="!help"))

class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot 
        self.song_queue = {}
        self.author = {}
        self.loop_condition = {}
        self.current_playing = {}
        self.known_limits = [
            "Can't Play Songs From Livestream",
            "Songs only come from youtube",
            "Skip To Currently Being Made"
        ]

        self.setup()

    def setup(self):
        for guild in self.bot.guilds:
            self.song_queue[guild.id] = []
            self.author[guild.id] = []
            self.loop_condition[guild.id] = [False , '']
            self.current_playing[guild.id] = ''
            
            
    async def search_song(self, amount, song, get_url=False):
        info = await self.bot.loop.run_in_executor(None, lambda: youtube_dl.YoutubeDL({"format" : "bestaudio", "quiet" : True}).extract_info(f"ytsearch{amount}:{song}", download=False, ie_key="YoutubeSearch"))
        if len(info["entries"]) == 0: return None

        return [entry["webpage_url"] for entry in info["entries"]] if get_url else info

    async def check_queue(self, ctx):
        thing = self.loop_condition[ctx.guild.id][0] 
        if thing == True :
            ctx.voice_client.stop()
            result = await self.search_song(1 , self.current_playing[ctx.guild.id] , get_url=True)
            song = result[0]
            await self.play_song(ctx , song  , self.loop_condition[ctx.guild.id][1])
            return 

        if len(self.song_queue[ctx.guild.id]) > 0:
            ctx.voice_client.stop()
            await self.play_song(ctx, self.song_queue[ctx.guild.id][0] , self.author[ctx.guild.id][0])
            self.author[ctx.guild.id].pop(0)
            self.song_queue[ctx.guild.id].pop(0)

        elif len(self.song_queue[ctx.guild.id]) == 0:
            await ctx.send('❌ Music queue ended.')
            await ctx.send('Disconnecting From Channel!')
            await ctx.voice_client.disconnect()
            self.loop_condition[ctx.guild.id] = False


    async def play_song(self, ctx, song , author):
        try:
            url = pafy.new(song).getbestaudio().url
            title = pafy.new(song).title
            embed = discord.Embed(colour=discord.Colour.dark_gold())
            embed.add_field(name = 'Now playing' , value=f' 🎶 {title}' , inline = False)
            user = ctx.message.guild.get_member(author)
            embed.set_thumbnail(url = user.avatar_url)
            embed.set_footer(text = f'Requested By : {user.name}')
            self.current_playing[ctx.guild.id] = title
            await ctx.send(embed=embed)
            ctx.voice_client.play(await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS), after=lambda error: self.bot.loop.create_task(self.check_queue(ctx)))
            ctx.voice_client.source.volume = 0.5

        except KeyError:
            await ctx.send(embed=discord.Embed(title="Song Couldn't Be Played",color = discord.Colour.red())) 

    @commands.command()
    async def loop(self , ctx):
        thing = self.loop_condition[ctx.guild.id][0]
        if thing == True :
            self.loop_condition[ctx.guild.id] = [False , ''] 
            return await ctx.send('🔁 Loop Is Now `OFF`')

        elif thing == False :
            self.loop_condition[ctx.guild.id] = [True , ctx.message.author.id]
            return await ctx.send('🔁 Loop Is Now `ON`')

            
    @commands.command()
    async def cq(self,ctx):
        self.song_queue[ctx.guild.id] = []
        ctx.voice_client.stop()
        await ctx.send(embed=discord.Embed(title="Queue Cleared" , colour=discord.Colour.dark_gold()))

    @commands.command()
    async def clear(self,ctx):
        self.song_queue[ctx.guild.id] = []
        ctx.voice_client.stop()
        await ctx.send(embed=discord.Embed(title="Queue Cleared" , colour=discord.Colour.dark_gold()))

    @commands.command()
    async def dc(self, ctx):
        if ctx.voice_client is not None:
            self.loop_condition[ctx.guild.id] = [False , '']
            return await ctx.voice_client.disconnect()
        await ctx.send(embed=discord.Embed(title='Im Not Connected To A VC' , colour = discord.Colour.red()))

    @commands.command()
    async def play(self,ctx,*,song=None):
        try:
            if ctx.author.voice is None:
                return ctx.send(embed=discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red()))

            elif ctx.voice_client == None:
                await ctx.author.voice.channel.connect()
                self.loop_condition[ctx.guild.id] = [False , '']

            elif ctx.author.voice.channel != ctx.voice_client.channel:
                return ctx.send(embed=discord.Embed(title="Connect To The Same VC As Me" , colour=discord.Colour.red()))

            else:
                await ctx.author.voice.channel.connect()
                self.loop_condition[ctx.guild.id] = [False , '']
                
        except ClientException:
            pass 
        
        thing = self.loop_condition[ctx.guild.id][0]
        if thing == True:
            return await ctx.send('❌Please Turn Off Loop, Then Play Music, Then Turn On Loop')


        if song is None:
            await ctx.send(embed=discord.Embed(title='Not Song Was Specified' , colour = discord.Colour.red()))


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
                self.author[ctx.guild.id].append(ctx.message.author.id)
                embed = discord.Embed(title='' , color = discord.Color.dark_gold())
                embed.add_field(name="Song Added", value=f"Song Has Been Added To Queue {queue_len+1}", inline=False)
                return await ctx.send(embed=embed)

            elif queue_len >= 10:
                return await ctx.send(embed = discord.Embed(title='Sorry, Only Up To 10 Queues' , color = discord.Color.red()))              
        
        await self.play_song(ctx, song , ctx.message.author.id)
    
    
    @commands.command()
    async def p(self, ctx, *, song=None):   
        try:
            if ctx.author.voice is None:
                return ctx.send(embed=discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red()))

            elif ctx.voice_client == None:
                await ctx.author.voice.channel.connect()
                self.loop_condition[ctx.guild.id] = [False , '']

            elif ctx.author.voice.channel != ctx.voice_client.channel:
                return ctx.send(embed=discord.Embed(title="Connect To The Same VC As Me" , colour=discord.Colour.red()))

            else:
                await ctx.author.voice.channel.connect()
                self.loop_condition[ctx.guild.id] = [False , '']
                
        except ClientException:
            pass 
        
        thing = self.loop_condition[ctx.guild.id][0]
        if thing == True:
            return await ctx.send('❌Please Turn Off Loop, Then Play Music, Then Turn On Loop')


        if song is None:
            await ctx.send(embed=discord.Embed(title='Not Song Was Specified' , colour = discord.Colour.red()))


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
                self.author[ctx.guild.id].append(ctx.message.author.id)
                embed = discord.Embed(title='' , color = discord.Color.dark_gold())
                embed.add_field(name="Song Added", value=f"Song Has Been Added To Queue {queue_len+1}", inline=False)
                return await ctx.send(embed=embed)

            elif queue_len >= 10:
                return await ctx.send(embed = discord.Embed(title='Sorry, Only Up To 10 Queues' , color = discord.Color.red()))              
        
        await self.play_song(ctx, song , ctx.message.author.id)


    @commands.command() 
    async def search(self, ctx, *, song=None):
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
        
    @commands.command()
    async def remove(self,ctx,index=None):
        if len(self.song_queue[ctx.guild.id])+1 < index or index <= 0:
            embed = discord.Embed(title='Invalid Number!' , colour=discord.Colour.red())
            return await ctx.send(embed = embed)

        elif index == None:
            embed = discord.Embed(title='Invalid Number!' , colour=discord.Colour.red())

        else:
            index -= 1 
            self.song_queue[ctx.guild.id].pop(index)
            embed = discord.Embed(title=f"Queue {index+1} Remove" , colour=discord.Colour.dark_gold())
            await ctx.send(embed=embed)
      

    @commands.command()
    async def dq(self,ctx,index=None):
        index = int(index)
        if len(self.song_queue[ctx.guild.id]) < index or index <= 0:
            embed = discord.Embed(title='Invalid Number!' , colour=discord.Colour.red())
            return await ctx.send(embed = embed)

        elif index == None:
            embed = discord.Embed(title='Invalid Number!' , colour=discord.Colour.red())

        else:
            index -= 1 
            self.song_queue[ctx.guild.id].pop(index)
            embed = discord.Embed(title=f"Queue {index+1} Remove" , colour=discord.Colour.dark_gold())
            await ctx.send(embed=embed)


    @commands.command()
    async def help(self,ctx):
        embed = discord.Embed(
            title = 'All Of The Commands',
            description = 'Enjoy The Bot!',
            colour = discord.Colour.dark_gold()
        )
        user = ctx.message.guild.get_member(ctx.message.author.id)
        embed.set_thumbnail(url = 'https://cdn.discordapp.com/avatars/887571515946704926/3155d1b7bebe8046697eca82d625f813.webp?size=64')
        embed.set_author(name = "Bird Music" , icon_url = 'https://cdn.discordapp.com/avatars/887571515946704926/3155d1b7bebe8046697eca82d625f813.webp?size=64')
        embed.add_field(name='`!play`' , value = 'Plays Any Song From Youtube | Aliases = !p' , inline = True)
        embed.add_field(name='`!queue`' , value = 'See What Is On Your Queue | Aliases = !q' , inline = True)
        embed.add_field(name='`!remove`' , value = 'Remove A Number On Queue | Aliases = !dq [number]' , inline = True)
        embed.add_field(name='`!skip`' , value = 'Skips Current Song To Next Song In Queue | Aliases = !stop , !s' , inline = True)
        embed.add_field(name='`!pause`' , value = 'Pauses Current Song | Aliases = None' , inline = True)
        embed.add_field(name='`!resume`' , value = 'Resumes Current Song | Aliases = None' , inline = True)
        embed.add_field(name='`!search`' , value = 'Search Videos To Find The Exact One You Want | Aliases = None' , inline = True)
        embed.add_field(name='`!clear`' , value = 'Clears The Queue | Aliases = cq' , inline = True)
        embed.add_field(name='`!join`' , value = 'Joins Your VC To Play Music | Aliases = None' , inline = True)
        embed.add_field(name='`!loop`' , value = 'Loops Current Playing Song | Aliases = None' , inline = True)
        embed.add_field(name='`!knownlimits`' , value = 'Shows all current known limitations | Aliases = !kl')
        embed.add_field(name = '**Links**' ,  value = '[Support Me](https://saweria.co/pZouLL) | [Official Website](https://youtube.com)' , inline = False)
        embed.set_footer(text = f'Requested By: {user.name}')
        return await ctx.send(embed=embed)

    @commands.command()
    async def knownlimits(self , ctx):
        embed = discord.Embed(title = 'Know Limitations' , description = '')
        user = ctx.message.guild.get_member(ctx.message.author.id)
        embed.set_thumbnail(url = user.avatar_url)
        for x in self.known_limits:
            embed.description += f'{x}\n'
        return await ctx.send(embed = embed)
        


    @commands.command()
    async def queue(self, ctx): # display the current guilds queue
        if len(self.song_queue[ctx.guild.id]) == 0:
            embed = discord.Embed(title='No Song In Queue' , colour=discord.Colour.dark_gold())
            return await ctx.send(embed=embed)

        embed = discord.Embed(title="Song Queue", description="", colour=discord.Colour.dark_gold())
        embed.description += f"**Currently Playing = {self.current_playing[ctx.guild.id]}**"
        i = 1
        for url in self.song_queue[ctx.guild.id]:
            video = pafy.new(url).title 
            embed.description += f"{i}) {video}\n"

            i += 1
        embed.set_thumbnail(url=ctx.guild.icon_url)
        user = ctx.message.guild.get_member(ctx.message.author.id)
        embed.set_footer(text = f'Requested By: {user.name}')
        await ctx.send(embed=embed)

    @commands.command()
    async def q(self, ctx): # display the current guilds queue
        if len(self.song_queue[ctx.guild.id]) == 0:
            embed = discord.Embed(title='No Song In Queue' , colour=discord.Colour.dark_gold())
            return await ctx.send(embed=embed)

        embed = discord.Embed(title="Song Queue", description="", colour=discord.Colour.dark_gold())
        i = 1
        for url in self.song_queue[ctx.guild.id]:
            video = pafy.new(url).title 
            embed.description += f"{i}) {video}\n"

            i += 1
        embed.set_thumbnail(url=ctx.guild.icon_url)
        user = ctx.message.guild.get_member(ctx.message.author.id)
        embed.set_footer(text = f'Requested By: {user.name}')
        await ctx.send(embed=embed)

    @commands.command()
    async def stop(self,ctx):
        if ctx.voice_client is None:
            embed = discord.Embed(title='Currently Not Playing Any Song' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice is None:
            embed = discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(title='Please Join The Same VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)


        await ctx.send(embed = discord.Embed(title='⏹ Music Skipped!' , colour=discord.Colour.dark_gold()))

    @commands.command()
    async def s(self, ctx):
        if ctx.voice_client is None:
            embed = discord.Embed(title='Currently Not Playing Any Song' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice is None:
            embed = discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(title='Please Join The Same VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)


        await ctx.send(embed = discord.Embed(title='⏹ Music Skipped!' , colour=discord.Colour.dark_gold()))


        ctx.voice_client.stop()


    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client is None:
            embed = discord.Embed(title='Currently Not Playing Any Song' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice is None:
            embed = discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(title='Please Join The Same VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)


        await ctx.send(embed = discord.Embed(title='⏹ Music Skipped!' , colour=discord.Colour.dark_gold()))


        ctx.voice_client.stop()

    @commands.command()
    async def pause(self, ctx):
        if ctx.voice_client.is_paused():
            return await ctx.send(embed = discord.Embed(title='Already Paused' , colour=discord.Colour.red()))

        if ctx.voice_client is None:
            embed = discord.Embed(title='Currently Not Playing Any Song' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice is None:
            embed = discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(title='Please Join The Same VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        ctx.voice_client.pause()
        await ctx.send(embed = discord.Embed("***Pause Succesfull***" , colour=discord.Colour.dark_gold()))


    @commands.command()
    async def resume(self, ctx):
        if ctx.voice_client is None:
            return await ctx.send(embed = discord.Embed(title='Connect Me To A VC' , colour=discord.Colour.red()))

        if not ctx.voice_client.is_paused():
            return await ctx.send(embed = discord.Embed(title='Already Playing Song' , colour=discord.Colour.red()))

        if ctx.voice_client is None:
            embed = discord.Embed(title='Currently Not Playing Any Song' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice is None:
            embed = discord.Embed(title='Please Connect To A VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)

        if ctx.author.voice.channel != ctx.voice_client.channel:
            embed = discord.Embed(title='Please Join The Same VC' , colour=discord.Colour.red())
            return await ctx.send(embed=embed)
        
        ctx.voice_client.resume()



        
async def setup():  
    await bot.wait_until_ready()
    bot.add_cog(Player(bot))

bot.loop.create_task(setup())

bot.run('yourmom')
