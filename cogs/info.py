import datetime
import time

import discord
from discord.ext import commands

import utils.globals as GG
from utils import logger

log = logger.logger


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.monotonic()

    @commands.command()
    @commands.guild_only()
    async def serverinfo(self, ctx):
        """Shows info about server"""
        HUMANS = ctx.guild.members
        BOTS = []
        for h in HUMANS:
            if h.bot is True:
                BOTS.append(h)
                HUMANS.remove(h)

        embed = discord.Embed(color=discord.Color.green())
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.add_field(name="Name", value=ctx.guild.name)
        embed.add_field(name="ID", value=ctx.guild.id)
        embed.add_field(name="Owner", value=f"{ctx.guild.owner.name}#{ctx.guild.owner.discriminator}")
        embed.add_field(name="Region", value=GG.REGION[ctx.guild.region])
        embed.add_field(name="Total | Humans | Bots", value=f"{len(ctx.guild.members)} | {len(HUMANS)} | {len(BOTS)}")
        embed.add_field(name="Verification Level", value=GG.V_LEVELS[ctx.guild.verification_level])
        text, voice = GG.count_channels(ctx.guild.channels)
        embed.add_field(name="Text Channels", value=str(text))
        embed.add_field(name="Voice Channels", value=str(voice))
        embed.add_field(name="Creation Date", value=f"{ctx.guild.created_at}\n{GG.check_days(ctx.guild.created_at)}")
        embed.set_thumbnail(url=ctx.guild.icon_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['stats', 'info'])
    async def botinfo(self, ctx):
        """Shows info about bot"""
        em = discord.Embed(color=discord.Color.green(),
                           description="~~DiscordCrawler~~ **SockBot**, a bot for moderation and other helpful things.")
        em.title = 'Bot Info'
        em.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)
        em.add_field(name="Servers", value=str(len(ctx.bot.guilds)))
        total_members = sum(len(s.members) for s in self.bot.guilds)
        unique_members = set(self.bot.get_all_members())
        members = '%s total\n%s unique' % (total_members, len(unique_members))
        em.add_field(name='Members', value=members)
        em.add_field(name='Uptime', value=str(datetime.timedelta(seconds=round(time.monotonic() - self.start_time))))
        totalText = 0
        totalVoice = 0
        for g in ctx.bot.guilds:
            text, voice = GG.count_channels(g.channels)
            totalText += text
            totalVoice += voice
        em.add_field(name='Text Channels', value=f"{totalText}")
        em.add_field(name='Voice Channels', value=f"{totalVoice}")
        em.add_field(name="Invite",
                     value="[Click Here](https://discord.com/api/oauth2/authorize?client_id=711472620994035743&permissions=268823632&scope=bot)")
        em.add_field(name='Source', value="[Click Here](https://github.com/robotski/DiscordCrawler)")
        em.add_field(name='Issue Tracker',
                     value="[Click Here](https://github.com/robotski/DiscordCrawler/issues)")
        em.add_field(name="About",
                     value='A multipurpose bot made by LordDusk#0001. Modified by Sock#2082.\n[Support Server](https://discord.gg/EMatTgMdna)')
        em.set_footer(text=f"SockBot {ctx.bot.version} | Powered by discord.py")
        await ctx.send(embed=em)

    @commands.command()
    async def support(self, ctx):
        em = GG.EmbedWithAuthor(ctx)
        em.title = 'Support Server'
        em.description = "So you want support for SockBot? You can easily join my discord [here](https://discord.gg/EMatTgMdna).\n" \
                         "This server allows you to ask questions about the bot. Do feature requests, and talk with other bot users!\n\n" \
                         "One more thing... You're pretty cool!"
        await ctx.send(embed=em)

    @commands.command()
    async def invite(self, ctx):
        em = GG.EmbedWithAuthor(ctx)
        em.title = 'Invite Me!'
        em.description = "Hi, you can easily invite me to your own server by following [this link](" \
                         "https://discord.com/api/oauth2/authorize?client_id=711472620994035743&permissions=268823632&scope=bot)!\n\nOf the 6 permissions asked, 5 are optional and 1 mandatory for optimal " \
                         "usage of the capabilities of the bot.\n\n**Mandatory:**\n__Manage Messages__ - this allows the " \
                         "bot to remove messages from other users.\n\n**Optional:**\n__Manage Webhooks__ - There are 2 " \
                         "ways for the quote command to function. One where it will use a webhook to give a reply as " \
                         "the person who quoted the message. Or one where it will just reply in text, but as the bot.\n\n" \
                         "__Attach Files__ - Some commands or replies will let the bot attach images/files, " \
                         "without this permission it will not be able too.\n\n" \
                         "__Add Reactions__ - For the Anon/Delivery the bot requires to be able to add reactions to " \
                         "messages that are send.\n\n" \
                         "__Manage Roles__ - For the Reaction Roles, the bot needs to be able to give users a role.\n\n" \
                         "__Read History__ - For some things to work (edit message, add reactions) the bot requires " \
                         "to be able to read the history of the channel. If it lacks this permission, but does have. " \
                         "Add Reactions, it will pelt you with 'Permission not found.'"
        await ctx.send(embed=em)

    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.is_owner()
    async def emojis(self, ctx):
        string = ""
        for x in ctx.guild.emojis:
            string += f"{x} -- ``{x}``\n"
            if (len(string) > 900):
                await ctx.send(string)
                string = ""
        await ctx.send(string)

    # @commands.command()
    # @commands.guild_only()
    # @GG.is_staff()
    # async def history(self, ctx, member = None):
    #     """[STAFF ONLY] Get the post history of an user."""
    #     if member is None:
    #         await ctx.send("Member can't be none. Proper command to use ``![history] [member]``")
    #     else:
    #         async with ctx.channel.typing():
    #             try:
    #                 user = await ctx.guild.fetch_member(member)
    #             except:
    #                 user = member
    #             guild = ctx.message.guild
    #             string = '{ "channels": ['
    #             for textChannel in guild.text_channels:
    #                 if ctx.guild.me.permissions_in(textChannel).read_messages:
    #                     string += '{ "' + str(textChannel) + '": ['
    #                     async for message in textChannel.history(limit=100, oldest_first=True):
    #                         if isinstance(user, str):
    #                             if message.author.id == user:
    #                                 string += '"' + str(message.content.replace('"', '\\"').replace('\n', '\\n')) + '",'
    #                         else:
    #                             if message.author == user:
    #                                 string += '"' + str(message.content.replace('"', '\\"').replace('\n', '\\n')) + '",'
    #                     if string[-1:] != '[':
    #                         string = string[:-1]
    #                     string += ']},'
    #             string = string[:-1]
    #             string += ']}'
    #             string = json.dumps(string)
    #             f = io.BytesIO(str.encode(string))
    #             file = discord.File(f, f"{user} - chatlog.json")
    #             await ctx.send(content=f"Messages (per channel, capped at 100) from ``{user}``\n*Note that it isn't a complete history, as Discord has some issues with their history api, so stuff may be missing.*" , file=file)


def setup(bot):
    log.info("[Cog] Info")
    bot.add_cog(Info(bot))
