import datetime
import re

from datetime import datetime

import discord
from discord import Colour
from models.quote_entry import QuoteModel, QuoteType, getQuoteEmbed, getQuoteAuthorEmbed
from discord.ext import commands

from disputils import BotEmbedPaginator

import utils.globals as GG
from utils import logger

log = logger.logger


async def get_next_quote_num():
    quoteNum = await GG.MDB['properties'].find_one({'key': 'quoteId'})
    num = quoteNum['amount'] + 1
    quoteNum['amount'] += 1
    await GG.MDB['properties'].replace_one({"key": 'quoteId'}, quoteNum)
    return num


class Quote(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot: discord.ext.commands.Bot = bot

    @commands.command(aliases=['oqa'])
    @commands.guild_only()
    async def oldquoteadd(self, ctx: commands.Context):
        def check(ms):
            return ctx.message.channel and ms.author == ctx.message.author

        await ctx.send("What would you like the quote to be?")
        message = await self.bot.wait_for('message', check=check)

        async with ctx.channel.typing():

            memberDB = await GG.MDB.members.find_one({"server": ctx.guild.id, "user": ctx.author.id})
            quoteId = await get_next_quote_num()

            if memberDB is None:
                memberDB = {"server": ctx.guild.id, "user": ctx.author.id, "quoteIds": [quoteId]}
            else:
                memberDB['quoteIds'].append(quoteId)

            # message = [word for line in message.clean_content.splitlines() for word in line.split()]
            member_list = []
            line_list = []
            try:
                curr = [[word for word in line.split(": ", 1)] for line in message.clean_content.splitlines()]
                for line in curr:
                    member = (await ctx.guild.query_members(line[0]))
                    if len(member) != 0:
                        member_list.append(member[0].id)
                    else:
                        member_list.append(line[0])
                    line_list.append(line[1])
            except:
                member_list = []
                line_list = []
                for line in message.clean_content.splitlines():
                    member_list.append(None)
                    line_list.append(line)

            quote = QuoteModel(quoteId, QuoteType.OLD, line_list, ctx.message.created_at, member_list, ctx.author.id)
            await GG.MDB.quote.insert_one(quote.to_dict())
            await GG.MDB.members.update_one({"server": ctx.guild.id, "user": ctx.author.id}, {"$set": memberDB}, upsert=True)
            embed = await getQuoteEmbed(ctx, quote)
            await ctx.send(embed=embed)




    @commands.command(aliases=['q'])
    @commands.guild_only()
    async def quote(self, ctx, msgId: int = None, *, reply=None):
        if not msgId:
            async with ctx.channel.typing():
                quote = QuoteModel.from_data([d async for d in GG.MDB.quote.aggregate([{'$sample': {'size': 1}}])][0])
                # quote = [d for d in GG.MDB.quote.aggregate([{"$sample": {"size": 1}}])][0]
                embed = await getQuoteEmbed(ctx, quote)
                await ctx.send(embed=embed)
                return

        if not isinstance(msgId, int):
            await ctx.send(content=":x:" + " **I work only with quote IDs.**")
            return



        # message = None
        # try:
        #     msgId = int(msgId)
        #     perms = ctx.guild.me.permissions_in(ctx.channel)
        # except ValueError:
        #     if perms.read_messages and perms.read_message_history:
        #         async for msg in ctx.channel.history(limit=100, before=ctx.message):
        #             if msgId.lower() in msg.content.lower():
        #                 message = msg
        #                 break
        # else:
        #     try:
        #         message = await ctx.channel.fetch_message(msgId)
        #     except:
        #         for channel in ctx.guild.text_channels:
        #             perms = ctx.guild.me.permissions_in(channel)
        #             if channel == ctx.channel or not perms.read_messages or not perms.read_message_history:
        #                 continue
        #
        #             try:
        #                 message = await channel.fetch_message(msgId)
        #             except:
        #                 continue
        #             else:
        #                 break
        #
        # if message:
        #     if not message.content and message.embeds and message.author.bot:
        #         await ctx.send(
        #             content='Raw embed from `' + str(message.author).strip('`') + '` in ' + message.channel.mention,
        #             embed=quote_embed(ctx.channel, message, ctx.author))
        #     else:
        #         await ctx.send(embed=quote_embed(ctx.channel, message, ctx.author))
        #
        #     if reply:
        #         if perms.manage_webhooks:
        #             webhook = await ctx.channel.create_webhook(name="Quoting")
        #             await webhook.send(content=reply.replace('@everyone', '@еveryone').replace('@here', '@hеre'),
        #                                username=ctx.author.display_name, avatar_url=ctx.author.avatar_url)
        #             await webhook.delete()
        #         else:
        #             await ctx.send(
        #                 content='**' + ctx.author.display_name + '\'s reply:**\n' + reply.replace('@everyone',
        #                                                                                           '@еveryone').replace(
        #                     '@here', '@hеre'))
        # else:
        #     await ctx.send(content=":x:" + ' **Could not find the specified message.**')


def parse_time(timestamp):
    if timestamp:
        return datetime.datetime(*map(int, re.split(r'[^\d]', timestamp.replace('+00:00', ''))))
    return None


def quote_embed(context_channel, message, user):
    if not message.content and message.embeds and message.author.bot:
        embed = message.embeds[0]
    else:
        uri = 'https://discordapp.com/channels/' + str(message.guild.id) + '/' + str(
            message.channel.id) + '/' + str(
            message.id)

        if message.channel != context_channel:
            message.content += f"\nQuoted by: {user} | in channel: #{message.channel.name} | [Direct Link]({uri})"
        else:
            message.content += f"\nQuoted by: {user} | [Direct Link]({uri})"

        if message.author not in message.guild.members or message.author.color == discord.Colour.default():
            embed = discord.Embed(description=message.content)
        else:
            embed = discord.Embed(description=message.content, color=message.author.color)
        if message.attachments:
            if message.channel.is_nsfw() and not context_channel.is_nsfw():
                embed.add_field(name='Attachments', value=':underage: **Quoted message belongs in NSFW channel.**')
            elif len(message.attachments) == 1 and message.attachments[0].url.lower().endswith(
                    ('.jpg', '.jpeg', '.png', '.gif', '.gifv', '.webp', '.bmp')):
                embed.set_image(url=message.attachments[0].url)
            else:
                for attachment in message.attachments:
                    embed.add_field(name='Attachment', value='[' + attachment.filename + '](' + attachment.url + ')',
                                    inline=False)

        embed.set_author(name=str(message.author), icon_url=message.author.avatar_url)

    return embed


def setup(bot):
    log.info("[Cog] Quote")
    bot.add_cog(Quote(bot))
