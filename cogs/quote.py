import datetime
import re
import traceback
from datetime import datetime

import discord
from discord.ext import commands

import utils.globals as gg
from models.quote_entry import QuoteModel, QuoteType, get_quote_embed
from utils import logger

log = logger.logger


async def get_next_quote_num():
    quote_num = await gg.MDB['properties'].find_one({'key': 'quoteId'})
    num = quote_num['amount'] + 1
    quote_num['amount'] += 1
    await gg.MDB['properties'].replace_one({"key": 'quoteId'}, quote_num)
    return num


async def save_quote(ctx, member_db, message, quote_id):
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
            except Exception as e:
                log.error(traceback.format_exc())
                del member_list[-1]
                if len(member_list) != len(line_list):
                    del line_list[-1]
                member_list.append(None)
                line_list.append(line[0])
        quote = QuoteModel(quote_id, QuoteType.OLD, line_list, ctx.message.created_at, member_list, ctx.author.id,
                           [None] * len(line_list))
        await gg.MDB.quote.insert_one(quote.to_dict())
        await gg.MDB.members.update_one({"server": ctx.guild.id, "user": ctx.author.id}, {"$set": member_db},
                                        upsert=True)
        embed = await get_quote_embed(ctx, quote)
        await ctx.send(embed=embed)


async def quote_db(ctx):
    member_db = await gg.MDB.members.find_one({"server": ctx.guild.id, "user": ctx.author.id})
    quote_id = await get_next_quote_num()
    if member_db is None:
        member_db = {"server": ctx.guild.id, "user": ctx.author.id, "quoteIds": [quote_id]}
    else:
        member_db['quoteIds'].append(quote_id)
    return member_db, quote_id


class Quote(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot: discord.ext.commands.Bot = bot
        self.active_quote = {}
        self.msg_id_list = {}

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        user = payload.user_id
        if user not in gg.RECORDERS:
            return
        if str(payload.emoji) == '📝':
            msg = await self.bot.get_channel(id=payload.channel_id).fetch_message(id=payload.message_id)
            index = self.active_quote[user][1].index(msg.clean_content)
            del self.active_quote[user][0][index]
            del self.active_quote[user][1][index]
            del self.active_quote[user][2][index]

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        user = payload.user_id
        message = payload.message_id
        if user not in gg.RECORDERS:
            return

        if gg.RECORDERS[user].id == message:
            if str(payload.emoji) == '❌':
                channel: discord.TextChannel = self.bot.get_channel(id=payload.channel_id)
                await gg.RECORDERS[user].delete()
                await channel.send("Canceled!")
                del gg.RECORDERS[user]
                del self.active_quote[user]
                return

            channel = self.bot.get_channel(id=payload.channel_id)
            ctx: discord.Message = gg.RECORDERS[user]

            if len(self.active_quote[user][0]) == 0:
                await channel.send(f"<@{user}> You didn't select any messages!")
                return

            member_db = await gg.MDB.members.find_one({"server": payload.guild_id, "user": user})
            quote_id = await get_next_quote_num()

            if member_db is None:
                member_db = {"server": payload.guild_id, "user": user, "quoteIds": [quote_id]}
            else:
                member_db['quoteIds'].append(quote_id)

            quote = QuoteModel(quote_id, QuoteType.NEW, self.active_quote[user][1], ctx.created_at,
                               self.active_quote[user][0], user, self.active_quote[user][2])
            await gg.MDB.quote.insert_one(quote.to_dict())
            await gg.MDB.members.update_one({"server": payload.guild_id, "user": user}, {"$set": member_db}, upsert=True)
            embed = await get_quote_embed(ctx, quote)
            await gg.RECORDERS[user].delete()
            await channel.send(embed=embed)
            del gg.RECORDERS[user]
            del self.active_quote[user]

            member = await self.bot.fetch_user(user)

            remove_channel = await self.channel_scan(ctx, user, self.msg_id_list[user][0])

            for msg_id in self.msg_id_list[user]:
                try:
                    to_remove = await remove_channel.fetch_message(msg_id)
                    await to_remove.remove_reaction('📝', member)
                except discord.errors.NotFound:
                    remove_channel = await self.channel_scan(ctx, user, msg_id)
                    to_remove = await remove_channel.fetch_message(msg_id)
                    await to_remove.remove_reaction('📝', member)

            del self.msg_id_list[user]

        if str(payload.emoji) == '📝':
            if user not in self.active_quote:
                self.active_quote[user] = [[], [], []]
            if user not in self.msg_id_list:
                self.msg_id_list[user] = []
            msg = await self.bot.get_channel(id=payload.channel_id).fetch_message(id=payload.message_id)
            member_db, line, jump_url = msg.author.id, msg.clean_content, msg.jump_url
            self.active_quote[user][0].append(member_db)
            self.active_quote[user][1].append(line)
            self.active_quote[user][2].append(jump_url)
            self.msg_id_list[user].append(msg.id)

    async def channel_scan(self, ctx, user, message):
        try:
            remove_channel = ctx.channel
            to_remove = await ctx.channel.fetch_message(message)
        except (ValueError, Exception):
            for remove_channel in ctx.guild.text_channels:
                perms = ctx.guild.me.permissions_in(remove_channel)
                if remove_channel == ctx.channel or not perms.read_messages or not perms.read_message_history:
                    continue
                try:
                    to_remove = await remove_channel.fetch_message(message)
                except (ValueError, Exception):
                    continue
                else:
                    break
        return remove_channel

    @commands.command(name="quoteadd", aliases=['qa', 'aq', 'addquote'])
    @commands.guild_only()
    async def quote_add(self, ctx: commands.Context, *, quote: str = None):
        if quote:
            member_db, quote_id = await quote_db(ctx)

            await save_quote(ctx, member_db, quote, quote_id)
            return

        if ctx.author.id in gg.RECORDERS:
            message = gg.RECORDERS[ctx.author.id]
            await ctx.send(embed=discord.Embed(
                description="You already have an active recorder [here]({link})".format(link=message.jump_url)))
            return
        message: discord.Message = await ctx.send(
            "Now recording. React to messages with 📝 to save them. Click ✅ to finish or ❌ to cancel.")
        gg.RECORDERS[ctx.author.id] = message
        if ctx.author.id not in self.active_quote:
            self.active_quote[ctx.author.id] = [[], [], []]
        await message.add_reaction('✅')
        await message.add_reaction('❌')

    @commands.command(name="oldquoteadd", aliases=['oqa', 'oaq', 'oldaddquote'])
    @commands.guild_only()
    async def old_quote_add(self, ctx: commands.Context, *, quote: str = None):
        def check(ms):
            return ctx.message.channel and ms.author == ctx.message.author

        member_db, quote_id = await quote_db(ctx)

        if quote:
            await save_quote(ctx, member_db, quote, quote_id)
            return

        await ctx.send("What would you like the quote to be?")
        message = await self.bot.wait_for('message', check=check)

        await save_quote(ctx, member_db, message.clean_content, quote_id)

    @commands.command(aliases=['q'])
    @commands.guild_only()
    async def quote(self, ctx, msg_id: int = None):
        if msg_id is None:
            async with ctx.channel.typing():
                quote = QuoteModel.from_data(await gg.MDB.quote.aggregate([{'$sample': {'size': 1}}]).next())
                embed = await get_quote_embed(ctx, quote)
                await ctx.send(embed=embed)
                return

        if not isinstance(msg_id, int):
            await ctx.send(content=":x:" + " **I work only with quote IDs.**")
            return

        if msg_id > 0:
            value = await gg.MDB.quote.find_one({"quoteId": msg_id})
        elif msg_id == 0:
            await ctx.send(content=":x:" + " **Quote selection has been reworked. -1 is the most recent, "
                                           "-2 is the second most, and so on.**")
            return
        else:
            value = await gg.MDB.quote.find().sort([("_id", -1)]).limit(-msg_id).skip(-msg_id - 1).next()
        if value is None:
            await ctx.send(content=":x:" + ' **Could not find the specified message.**')
            return
        quote = QuoteModel.from_data(value)
        embed = await get_quote_embed(ctx, quote)
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
