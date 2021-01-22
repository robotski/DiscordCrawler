import datetime
import re
from datetime import datetime

import discord
from discord.ext import commands

import utils.globals as GG
from models.quote_entry import QuoteModel, QuoteType, getQuoteEmbed
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
        self.active_quote = {}

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        user = payload.user_id
        if user not in GG.RECORDERS:
            return
        if str(payload.emoji) == '📝':
            msg = await self.bot.get_channel(id=payload.channel_id).fetch_message(id=payload.message_id)
            index = self.active_quote[user][1].index(msg.clean_content)
            del self.active_quote[user][0][index]
            del self.active_quote[user][1][index]

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        user = payload.user_id
        message = payload.message_id
        if user not in GG.RECORDERS:
            return
        if GG.RECORDERS[user].id == message:
            if str(payload.emoji) == '❌':
                channel: discord.TextChannel = self.bot.get_channel(id=payload.channel_id)
                await GG.RECORDERS[user].delete()
                await channel.send("Canceled!")
                del GG.RECORDERS[user]
                del self.active_quote[user]
                return
            channel = self.bot.get_channel(id=payload.channel_id)
            ctx: discord.Message = GG.RECORDERS[user]

            if len(self.active_quote[user][0]) == 0:
                await channel.send(f"<@{user}> You didn't select any messages!")
                return

            memberDB = await GG.MDB.members.find_one({"server": payload.guild_id, "user": user})
            quoteId = await get_next_quote_num()

            if memberDB is None:
                memberDB = {"server": payload.guild_id, "user": user, "quoteIds": [quoteId]}
            else:
                memberDB['quoteIds'].append(quoteId)

            quote = QuoteModel(quoteId, QuoteType.NEW, self.active_quote[user][1], ctx.created_at,
                               self.active_quote[user][0], user)
            await GG.MDB.quote.insert_one(quote.to_dict())
            await GG.MDB.members.update_one({"server": payload.guild_id, "user": user}, {"$set": memberDB}, upsert=True)
            embed = await getQuoteEmbed(ctx, quote)
            await GG.RECORDERS[user].delete()
            await channel.send(embed=embed)
            del GG.RECORDERS[user]
            del self.active_quote[user]
        if str(payload.emoji) == '📝':
            if user not in self.active_quote:
                self.active_quote[user] = [[], []]
            msg = await self.bot.get_channel(id=payload.channel_id).fetch_message(id=payload.message_id)
            member, line = msg.author.id, msg.clean_content
            self.active_quote[user][0].append(member)
            self.active_quote[user][1].append(line)

    @commands.command(aliases=['qa', 'aq'])
    @commands.guild_only()
    async def quoteadd(self, ctx: commands.Context, *, quote: str = None):
        if quote:
            memberDB = await GG.MDB.members.find_one({"server": ctx.guild.id, "user": ctx.author.id})
            quoteId = await get_next_quote_num()

            if memberDB is None:
                memberDB = {"server": ctx.guild.id, "user": ctx.author.id, "quoteIds": [quoteId]}
            else:
                memberDB['quoteIds'].append(quoteId)

            await self.save_quote(ctx, memberDB, quote, quoteId)
            return

        if ctx.author.id in GG.RECORDERS:
            message = GG.RECORDERS[ctx.author.id]
            await ctx.send(embed=discord.Embed(
                description="You already have an active recorder [here]({link})".format(link=message.jump_url)))
            return
        message: discord.Message = await ctx.send(
            "Now recording. React to messages with 📝 to save them. Click ✅ to finish or ❌ to cancel.")
        GG.RECORDERS[ctx.author.id] = message
        if ctx.author.id not in self.active_quote:
            self.active_quote[ctx.author.id] = [[], []]
        await message.add_reaction('✅')
        await message.add_reaction('❌')

    @commands.command(aliases=['oqa'])
    @commands.guild_only()
    async def oldquoteadd(self, ctx: commands.Context, *, quote: str = None):
        def check(ms):
            return ctx.message.channel and ms.author == ctx.message.author

        memberDB = await GG.MDB.members.find_one({"server": ctx.guild.id, "user": ctx.author.id})
        quoteId = await get_next_quote_num()

        if memberDB is None:
            memberDB = {"server": ctx.guild.id, "user": ctx.author.id, "quoteIds": [quoteId]}
        else:
            memberDB['quoteIds'].append(quoteId)

        if quote:
            await self.save_quote(ctx, memberDB, quote, quoteId)
            return

        await ctx.send("What would you like the quote to be?")
        message = await self.bot.wait_for('message', check=check)

        await self.save_quote(ctx, memberDB, message.clean_content, quoteId)

    async def save_quote(self, ctx, memberDB, message, quoteId):
        async with ctx.channel.typing():
            member_list = []
            line_list = []
            curr = [[word for word in line.split(": ", 1)] for line in message.splitlines()]
            for line in curr:
                try:
                    member = (await ctx.guild.query_members(line[0]))
                    if len(member) != 0:
                        member_list.append(member[0].id)
                    else:
                        member_list.append(line[0])
                    line_list.append(line[1])
                except:
                    del member_list[-1]
                    if len(member_list) != len(line_list):
                        del line_list[-1]
                    member_list.append(None)
                    line_list.append(line[0])
            quote = QuoteModel(quoteId, QuoteType.OLD, line_list, ctx.message.created_at, member_list, ctx.author.id)
            await GG.MDB.quote.insert_one(quote.to_dict())
            await GG.MDB.members.update_one({"server": ctx.guild.id, "user": ctx.author.id}, {"$set": memberDB},
                                            upsert=True)
            embed = await getQuoteEmbed(ctx, quote)
            await ctx.send(embed=embed)

    @commands.command(aliases=['q'])
    @commands.guild_only()
    async def quote(self, ctx, msgId: int = None, *, reply=None):
        if msgId is None:
            async with ctx.channel.typing():
                quote = QuoteModel.from_data(await GG.MDB.quote.aggregate([{'$sample': {'size': 1}}]).next())
                embed = await getQuoteEmbed(ctx, quote)
                await ctx.send(embed=embed)
                return

        if not isinstance(msgId, int):
            await ctx.send(content=":x:" + " **I work only with quote IDs.**")
            return

        if msgId > 0:
            value = await GG.MDB.quote.find_one({"quoteId": msgId})
        elif msgId == 0:
            await ctx.send(
                content=":x:" + ' **Quote selection has been reworked. -1 is the most recent, -2 is the second most, and so on.**')
            return
        else:
            value = await GG.MDB.quote.find().sort([("_id", -1)]).limit(-msgId).skip(-msgId - 1).next()
        if value is None:
            await ctx.send(content=":x:" + ' **Could not find the specified message.**')
            return
        quote = QuoteModel.from_data(value)
        embed = await getQuoteEmbed(ctx, quote)
        await ctx.send(embed=embed)
        return


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
