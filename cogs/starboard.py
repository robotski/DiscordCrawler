from discord.ext import commands

import utils.globals as GG
from utils import logger
import logging
import asyncio
from typing import Dict, Literal, Union, cast, Optional
from datetime import datetime, timedelta

import discord
from discord.utils import snowflake_time
import discord

from typing import Dict, Union, cast, Optional

from models.starboard_entry import StarboardEntry, StarboardMessage, FakePayload

log = logger.logger

from discord.ext.commands.converter import Converter
from discord.ext.commands.errors import BadArgument

class StarboardExists(Converter):
    async def convert(self, ctx: commands.Context, argument: str) -> StarboardEntry:
        cog = ctx.cog
        guild = ctx.guild
        if guild.id not in cog.starboards:
            raise BadArgument("There are no starboards setup on this server!")
        try:
            starboard = cog.starboards[guild.id][argument.lower()]
        except KeyError:
            raise BadArgument("There is no starboard named {name}".format(name=argument))
        return starboard




def getGuild(self, payload):
    guild = self.bot.get_guild(payload.guild_id)
    return guild


class Starboard(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    async def _build_starboard_info(self, ctx: commands.Context, starboard: StarboardEntry):
        channel_perms = ctx.channel.permissions_for(ctx.guild.me)
        embed = discord.Embed(colour=await self._get_colour(ctx.channel))
        embed.title = "Starboard settings for {guild}".format(guild=ctx.guild.name)
        text_msg = ""
        channel = ctx.guild.get_channel(starboard.channel)
        s_channel = channel.mention if channel else "deleted_channel"
        msg = "Name: {name}\n".format(name=starboard.name)
        msg += "Enabled: {enabled}\n".format(enabled=starboard.enabled)
        msg += "Emoji: {emoji}\n".format(emoji=starboard.emoji)
        msg += "Channel: {channel}\n".format(channel=s_channel)
        msg += "Threshold: {threshold}\n".format(threshold=starboard.threshold)
        if starboard.blacklist_channel:
            channels = [ctx.guild.get_channel(c) for c in starboard.blacklist_channel]
            chans = ", ".join(c.mention for c in channels if c is not None)
            msg += "Blocked Channels: {chans}\n".format(chans=chans)
        if starboard.whitelist_channel:
            channels = [ctx.guild.get_channel(c) for c in starboard.whitelist_channel]
            chans = ", ".join(c.mention for c in channels if c is not None)
            msg += "Allowed Channels: {chans}\n".format(chans=chans)
        if starboard.blacklist_role:
            roles = [ctx.guild.get_role(c) for c in starboard.blacklist_role]
            if channel_perms.embed_links:
                chans = ", ".join(r.mention for r in roles if r is not None)
            else:
                chans = ", ".join(r.name for r in roles if r is not None)
            msg += "Blocked roles: {chans}\n".format(chans=chans)
        if starboard.whitelist_role:
            roles = [ctx.guild.get_role(c) for c in starboard.whitelist_role]
            if channel_perms.embed_links:
                chans = ", ".join(r.mention for r in roles)
            else:
                chans = ", ".join(r.name for r in roles)
            msg += "Allowed Roles: {chans}\n".format(chans=chans)
        embed.add_field(name=_("Starboard {name}").format(name=starboard.name), value=msg)
        text_msg += "{msg} Starboard {name}\n".format(msg=msg, name=starboard.name)
        return (embed, text_msg)


    async def _check_roles(self, starboard: StarboardEntry, member: Union[discord.Member, discord.User]) -> bool:
        if not isinstance(member, discord.Member):
            return True
        user_roles = set([role.id for role in member.roles])
        if starboard.whitelist_role:
            for role in starboard.whitelist_role:
                if role in user_roles:
                    return True
            return False

        return True

    async def _check_channel(self, starboard: StarboardEntry, channel: discord.TextChannel) -> bool:
        if channel.is_nsfw() and not self.bot.get_channel(starboard.channel).is_nsfw():
            return False
        if starboard.whitelist_channel:
            if channel.id in starboard.whitelist_channel:
                return True
            if channel.category_id and channel.category_id in starboard.whitelist_channel:
                return True
            return False
        else:
            if channel.id in starboard.blacklist_channel:
                return False
            if channel.category_id and channel.category_id in starboard.blacklist_channel:
                return False
            return True

    async def _build_embed(self, guild: discord.Guild, message: discord.Message, starboard: StarboardEntry) -> discord.Embed:
        channel = cast(discord.TextChannel, message.channel)
        author = message.author
        if message.embeds:
            em = message.embeds[0]
            if message.system_content:
                if em.description != discord.Embed.Empty:
                    em.description = "{}\n\n{}".format(message.system_content, em.description)[:2048]
                else:
                    em.description = message.system_content
                if not author.bot:
                    em.set_author(name=author.display_name, url=message.jump_url, icon_url=str(author.avatar_url))
        else:
            em = discord.Embed(timestamp=message.created_at)
            em.color = author.color
            em.description = message.system_content
            em.set_author(name=author.display_name, url=message.jump_url, icon_url=str(author.avatar_url))
            if message.attachments != []:
                em.set_image(url=message.attachments[0].url)
        em.timestamp = message.created_at
        jump_link = "\n\n[Click Here to view context]({link})".format(link=message.jump_url)
        if em.description:
            em.description = f"{em.description}{jump_link}"
        else:
            em.description = jump_link
        em.set_footer(text=f"{channel.guild.name} | {channel.name}")
        return em

    async def _get_count(self, message_entry: StarboardMessage, starboard: StarboardEntry, remove: Optional[int]) -> StarboardMessage:
        orig_channel = self.bot.get_channel(message_entry.original_channel)
        new_channel = self.bot.get_channel(message_entry.new_channel)
        orig_reaction = []
        if orig_channel:
            try:
                orig_msg = await orig_channel.fetch_message(message_entry.original_message)
                orig_reaction = [r for r in orig_msg.reactions if str(r.emoji) == str(starboard.emoji)]
            except discord.errors.Forbidden:
                pass
        new_reaction = []
        if new_channel:
            try:
                new_msg = await new_channel.fetch_message(message_entry.new_message)
                new_reaction = [r for r in new_msg.reactions if str(r.emoji) == str(starboard.emoji)]
            except discord.errors.Forbidden:
                pass

        reactions = orig_reaction + new_reaction
        for reaction in reactions:
            log.debug(reactions)
            async for user in reaction.users():
                if user.id == orig_msg.author.id:
                    continue
                if user.id not in message_entry.reactions and not user.bot:
                    log.debug("Adding user")
                    message_entry.reactions.append(user.id)
        if remove and remove in message_entry.reactions:
            log.debug("Removing user")
            message_entry.reactions.remove(remove)
        message_entry.reactions = list(set(message_entry.reactions))
        log.debug(message_entry.reactions)
        return message_entry


    async def _loop_messages(self, payload: Union[discord.RawReactionActionEvent, FakePayload], starboard: StarboardEntry, star_channel: discord.TextChannel, message: discord.Message, remove: Optional[int]) -> bool:
        try:
            guild = star_channel.guild
        except AttributeError:
            return True
        for messages in starboard.messages:
            same_message = messages.original_message == message.id
            same_channel = messages.original_channel == payload.channel_id
            starboard_message = messages.new_message == message.id
            starboard_channel = messages.new_channel == payload.channel_id

            if not messages.new_message or not messages.new_channel:
                continue
            if (same_message and same_channel) or (starboard_message and starboard_channel):
                await self._get_count(messages, starboard, remove)
                if remove is None:
                    if getattr(payload, "user_id", 0) not in messages.reactions:
                        log.debug("Adding user in _loop_messages")
                        messages.reactions.append(payload.user_id)
                count = len(messages.reactions)
                log.debug(messages.reactions)
                try:
                    message_edit = await star_channel.fetch_message(messages.new_message)
                except (discord.errors.NotFound, discord.errors.Forbidden):
                    return True
                if count < 2:
                    messages.new_message = None
                    messages.new_channel = None
                    await self._save_starboards(guild)
                    await message_edit.delete()
                    return True
                log.debug("Editing starboard")
                count_message = f"{starboard.emoji} **#{count}**"
                await message_edit.edit(content=count_message)
                return True
            return False


    @commands.command()
    @commands.guild_only()
    @GG.is_staff()
    async def addStarboard(self, ctx: commands.Context, name: str, channel: discord.TextChannel = None, emoji: Union[discord.Emoji, str] = "⭐", ) -> None:
        guild = ctx.message.guild
        name = name.lower()
        if channel is None:
            channel = ctx.message.channel
            if type(emoji) == discord.Emoji:
                if emoji not in guild.emojis:
                    await ctx.send("That emoji is not on this guild!")
                    return
        if not channel.permissions_for(guild.me).send_messages:
            send_perms = "I don't have permission to post in "

            await ctx.send(send_perms + channel.mention)
            return

        if not channel.permissions_for(guild.me).embed_links:
            embed_perms = "I don't have permission to embed links in "
            await ctx.send(embed_perms + channel.mention)
            return
        if guild.id not in GG.STARBOARDS:
            GG.STARBOARDS[guild.id] = {}
        starboards = GG.STARBOARDS[guild.id]
        if name in starboards:
            await ctx.send("{name} starboard name is already being used".format(name=name))
            return
        starboard = StarboardEntry(name=name, channel=channel.id, emoji=str(emoji))
        starboards[name] = starboard
        await self._save_starboards(guild)
        msg = "Starboard set to {channel} with emoji {emoji}".format(channel=channel.mention, emoji=emoji)
        await ctx.send(msg)


    @commands.command()
    @commands.guild_only()
    @GG.is_staff()
    async def removeStarboard(self, ctx: commands.Context, starboard: Optional[StarboardExists]) -> None:
        guild = ctx.guild
        if not starboard:
            if guild.id not in GG.STARBOARDS:
                await ctx.send("There are no starboards setup on this server!")
                return
            if len(GG.STARBOARDS[guild.id]) > 1:
                await ctx.send("There's more than one starboard setup in this server. " "Please provide a name for the starboard you wish to use.")
                return
            starboard = list(GG.STARBOARDS[guild.id].values())[0]
        del GG.STARBOARDS[ctx.guild.id][starboard.name]
        await self._save_starboards(ctx.guild)
        await ctx.send("Deleted starboard {name}".format(name=starboard.name))


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        await self._update_stars(payload)


    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        await self._update_stars(payload, remove=payload.user_id)


    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionActionEvent) -> None:
        channel = self.bot.get_channel(id=payload.channel_id)
        try:
            guild = channel.guild
        except AttributeError:
            return
        try:
            msg = await channel.fetch_message(id=payload.message_id)
        except (discord.errors.NotFound, discord.Forbidden):
            return
        if guild.id not in GG.STARBOARDS:
            return
        for name, starboard in GG.STARBOARDS[guild.id].items():
            star_channel = self.bot.get_channel(starboard.channel)
            if not star_channel:
                continue
            async with starboard.lock:
                await self._loop_messages(payload, starboard, star_channel, msg, None)

    async def _save_starboards(self, guild: discord.Guild) -> None:
        await GG.MDB['starboards'].replace_one({'guild': guild.id}, {'guild': guild.id,'starboards': {n: s.to_json() for n, s in GG.STARBOARDS[guild.id].items()}}, upsert=True)

    async def _update_stars(self, payload: Union[discord.RawReactionActionEvent, FakePayload], remove: Optional[int] = None) -> None:
        channel = self.bot.get_channel(id=payload.channel_id)
        try:
            guild = channel.guild
        except AttributeError:
            return
        if guild.id not in GG.STARBOARDS:
            return

        member = guild.get_member(payload.user_id)
        if member and member.bot:
            return
        starboard = None
        for name, s_board in GG.STARBOARDS[guild.id].items():
            if s_board.emoji == str(payload.emoji):
                starboard = s_board
        if not starboard:
            return

        star_channel = guild.get_channel(starboard.channel)
        if not star_channel:
            return
        try:
            msg = await channel.fetch_message(id=payload.message_id)
        except (discord.errors.NotFound, discord.Forbidden):
            return
        if member.id == msg.author.id:
            return
        async with starboard.lock:
            if await self._loop_messages(payload, starboard, star_channel, msg, remove):
                return

            star_message = StarboardMessage(original_message=msg.id, original_channel=channel.id, new_message=None, new_channel=None, author=msg.author.id, reactions=[payload.user_id])
            await self._get_count(star_message, starboard, remove)
            count = len(star_message.reactions)
            if count < 2:
                if star_message not in starboard.messages:
                    GG.STARBOARDS[guild.id][starboard.name].messages.append(star_message)
                await self._save_starboards(guild)
                return
            em = await self._build_embed(guild, msg, starboard)
            count_msg = "{} **#{}**".format(payload.emoji, count)
            post_msg = await star_channel.send(count_msg, embed=em)
            if star_message not in starboard.messages:
                GG.STARBOARDS[guild.id][starboard.name].messages.append(star_message)
            star_message.new_message = post_msg.id
            star_message.new_channel = star_channel.id
            GG.STARBOARDS[guild.id][starboard.name].messages.append(star_message)
            await self._save_starboards(guild)


def setup(bot):
    log.info("[Cog] Starboard")
    bot.add_cog(Starboard(bot))
