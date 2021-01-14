import discord
from discord.ext import commands

import utils.globals as GG
from utils import logger

import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional, Union
from typing import Dict, Literal, Union, cast, Optional

log = logger.logger

@dataclass
class StarboardMessage:
    """A class to hold message objects pertaining
    To starboarded messages including the original
    message ID, and the starboard message ID
    as well as a list of users who have added their "vote"
    """

    def __init__(self, **kwargs):
        self.original_message: int = kwargs.get("original_message")
        self.original_channel: int = kwargs.get("original_channel")
        self.new_message: Optional[int] = kwargs.get("new_message")
        self.new_channel: Optional[int] = kwargs.get("new_channel")
        self.author: int = kwargs.get("author")
        self.reactions: List[int] = kwargs.get("reactions")

    def to_json(self) -> dict:
        return {
            "original_message": self.original_message,
            "original_channel": self.original_channel,
            "new_message": self.new_message,
            "new_channel": self.new_channel,
            "author": self.author,
            "reactions": self.reactions,
        }

    @classmethod
    def from_json(cls, data: dict):
        reactions = []
        if "reactions" in data:
            reactions = data["reactions"]
        return cls(
            original_message=data["original_message"],
            original_channel=data["original_channel"],
            new_message=data["new_message"],
            new_channel=data["new_channel"],
            author=data["author"],
            reactions=reactions,
        )



def getGuild(self, payload):
    guild = self.bot.get_guild(payload.guild_id)
    return guild


class Starboard(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot

    async def _build_embed(self, guild: discord.Guild, message: discord.Message) -> discord.Embed:
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
                    em.set_author(name=author.display_name, url=message.jump_url, icon_url=str(author.avatar_url), )
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

    async def _get_count(self, message_entry: StarboardMessage, emoji: discord.Emoji, remove: Optional[int]) -> StarboardMessage:
        orig_channel = self.bot.get_channel(message_entry.original_channel)
        new_channel = self.bot.get_channel(message_entry.new_channel)
        orig_reaction = []
        if orig_channel:
            try:
                orig_msg = await orig_channel.fetch_message(message_entry.original_message)
                orig_reaction = [r for r in orig_msg.reactions if str(r.emoji) == str(emoji)]
            except discord.errors.Forbidden:
                pass
        new_reaction = []
        if new_channel:
            try:
                new_msg = await new_channel.fetch_message(message_entry.new_message)
                new_reaction = [r for r in new_msg.reactions if str(r.emoji) == str(emoji)]
            except discord.errors.Forbidden:
                pass

        reactions = orig_reaction + new_reaction
        for reaction in reactions:
            log.debug(reactions)
            async for user in reaction.users():
                if user.id not in message_entry.reactions and not user.bot:
                    log.debug("Adding user")
                    message_entry.reactions.remove(remove)
                message_entry.reactions= list(set(message_entry.reactions))
                log.debug(message_entry.reactions)
                return message_entry


    async def _scan_messages(self, payload: discord.RawReactionActionEvent, star_channel: discord.TextChannel, message: discord.Message) -> bool:
        curr_message = await GG.MDB['starboardmessages'].find_one({'original_message': message.id})
        if curr_message is not None:
            curr_message = StarboardMessage.from_json(curr_message)
            if not curr_message.new_message or not curr_message.new_channel:
                return False
            count = len(curr_message.reactions)
            log.debug(curr_message.reactions)
            try:
                message_edit = await star_channel.fetch_message(curr_message.new_message)
            except (discord.errors.NotFound, discord.errors.Forbidden):
                # starboard message may have been deleted
                return True
            if count < 2:
                curr_message.new_message = None
                curr_message.new_channel = None
                await GG.MDB['starboardmessages'].replace_one({'original_message': curr_message.original_message}, curr_message.to_json(), upsert=True)
                await message_edit.delete()
                return True
            log.debug("Editing starboard")
            count_message = f"{payload.emoji} **#{count}**"
            await message_edit.edit(content=count_message)
            return True
        return False

    @commands.command()
    @commands.guild_only()
    @GG.is_staff()
    async def addStarboard(self, ctx: commands.Context, channel: discord.TextChannel = None,
                           emoji: Union[discord.Emoji, str] = "⭐", ) -> None:
        guild = ctx.message.guild
        if channel is None:
            channel = ctx.message.channel
        if type(emoji) == discord.Emoji:
            if emoji not in guild.emojis:
                await ctx.send("That emoji is not on this guild!")
                return
        if not channel.permissions_for(guild.me).send_messages:
            send_perms = "I don't permission to post in "

            await ctx.send(send_perms + channel.mention)
            return

        if not channel.permissions_for(guild.me).embed_links:
            embed_perms = "I don't have permission to embed links in "
            await ctx.send(embed_perms + channel.mention)
            return
        # if guild.id not in self.starboards:
        #     self.starboards[guild.id] = {}
        # starboards = self.starboards[guild.id]
        # if channel in starboards:
        #     await ctx.send(_("{channel} starboard is already being used").format(channel=channel))
        #     return
        # starboard = StarboardEntry(channel=channel.id, emoji=str(emoji))
        # starboards[channel] = starboard
        # await self._save_starboards(guild)
        result = GG.MDB['starboards'].find({"guild": guild.id, "channel": channel.id})
        if await result.fetch_next:
            await ctx.send("{channel} starboard is already being used".format(channel=channel))
            return
        else:
            await GG.MDB['starboards'].insert_one({"guild": guild.id, "channel": channel.id, "emoji": str(emoji)})
            GG.STARBOARDS = await GG.reloadStarboards()
        msg = "Starboard set to {channel} with emoji {emoji}".format(channel=channel.mention, emoji=emoji)
        await ctx.send(msg)

    @commands.command()
    @commands.guild_only()
    @GG.is_staff()
    async def removeStarboard(self, ctx: commands.Context, channel: discord.TextChannel = None) -> None:
        guild = ctx.guild
        if channel is None:
            await ctx.send("Please provide a channel ID for the starboard you wish to delete.")
            return
        result = GG.MDB['starboards'].find({"guild": guild.id, "channel": channel.id})
        if await result.fetch_next:
            await GG.MDB['starboards'].delete_one({"guild": guild.id, "channel": channel.id})
            await ctx.send("Deleted starboard {channel}".format(channel=channel))
        else:
            await ctx.send("Starboard with that ID does not exist")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        channel = self.bot.get_channel(id=payload.channel_id)

        if str(payload.guild_id) + str(payload.emoji) in GG.STARBOARDS:
            emoji = payload.emoji
            guild = channel.guild
            star_channel = guild.get_channel(GG.STARBOARDS[str(payload.guild_id) + str(payload.emoji)][0])

            member = guild.get_member(payload.user_id)
            if member and member.bot:
                return

            msg = await channel.fetch_message(id=payload.message_id)

            # if member.id == msg.author.id:
            #     return

            if await self._scan_messages(payload, star_channel, msg):
                return

            star_message = StarboardMessage(
                original_message = msg.id,
                original_channel = channel.id,
                new_message = None,
                new_channel = None,
                author = msg.author.id,
                reactions = [payload.user_id],
            )

            count = discord.utils.get(msg.reactions, emoji=emoji.name).count
            if count < 2:
                # checkIfExist = await GG.MDB['starboardmessages'].find_one(star_message.to_json())
                checkIfExist = await GG.MDB['starboardmessages'].find_one({'original_message': star_message.original_message})
                if checkIfExist is not None:
                    # it's already in the db
                    pass
                else:
                    # await GG.MDB['starboardmessages'].update_one({"message": star_message.to_json()}, upsert=True)
                    await GG.MDB['starboardmessages'].replace_one({'original_message': star_message.original_message}, star_message.to_json(), upsert=True)
                return
            em = await self._build_embed(guild, msg)
            count_msg = "{} **#{}**".format(payload.emoji, int(count))
            post_msg = await star_channel.send(count_msg, embed=em)
            checkIfExist = await GG.MDB['starboardmessages'].find_one({'original_message': star_message.original_message})
            if checkIfExist is not None:
                # it's already in the db
                pass
            else:
                # await GG.MDB['starboardmessages'].update_one({"message": star_message}, upsert=True)
                await GG.MDB['starboardmessages'].replace_one({'original_message': star_message.original_message}, star_message.to_json(), upsert=True)
            star_message.new_message = post_msg.id
            star_message.new_channel = star_channel.id
            # await GG.MDB['starboardmessages'].update_one({"message": star_message}, upsert=True)
            await GG.MDB['starboardmessages'].replace_one({'original_message': star_message.original_message}, star_message.to_json(), upsert=True)

        # if star_message not in starboard.messages:
        # count = msg.get_reactions
        # channel = self.bot.get_channel(id=payload.channel_id)
        # result = GG.MDB['starboards'].find({"guild": guild.id})
        # if not await result.fetch_next:
        #     return
        #
        # # starboard = GG.MDB['starboards'].find({"guild": guild.id, "emoji": str(payload.emoji)})['channel']

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        channel = self.bot.get_channel(id=payload.channel_id)

        if str(payload.guild_id) + str(payload.emoji) in GG.STARBOARDS:
            guild = channel.guild
            star_channel = guild.get_channel(GG.STARBOARDS[str(payload.guild_id) + str(payload.emoji)][0])

            member = guild.get_member(payload.user_id)
            if member and member.bot:
                return

            msg = await channel.fetch_message(id=payload.message_id)

            # if member.id == msg.author.id:
            #     return

            if await self._scan_messages(payload, star_channel, msg):
                return



# @dataclass
# class StarboardEntry:
#     def __init__(self, **kwargs):
#
#         super().__init__()
#         self.name: str = kwargs.get("name")
#         self.channel: int = kwargs.get("channel")
#         self.emoji: str = kwargs.get("emoji")
#         self.colour: str = kwargs.get("colour", "user")
#         self.enabled: bool = kwargs.get("enabled", True)
#         self.selfstar: bool = kwargs.get("selfstar", False)
#         self.blacklist_role: List[int] = kwargs.get("blacklist_role", [])
#         self.whitelist_role: List[int] = kwargs.get("whitelist_role", [])
#         self.messages: List[StarboardMessage] = kwargs.get(
#             "messages", []
#         )
#         self.blacklist_channel: List[int] = kwargs.get("blacklist_channel", [])
#         self.whitelist_channel: List[int] = kwargs.get("whitelist_channel", [])
#         self.threshold: int = kwargs.get("threshold", 1)
#         self.autostar: bool = kwargs.get("autostar", False)
#         self.lock: asyncio.Lock = asyncio.Lock()
#
#     def to_json(self) -> dict:
#         return {
#             "name": self.name,
#             "enabled": self.enabled,
#             "channel": self.channel,
#             "emoji": self.emoji,
#             "colour": self.colour,
#             "selfstar": self.selfstar,
#             "blacklist_role": self.blacklist_role,
#             "whitelist_role": self.whitelist_role,
#             "messages": [m.to_json() for m in self.messages],
#             "blacklist_channel": self.blacklist_channel,
#             "whitelist_channel": self.whitelist_channel,
#             "threshold": self.threshold,
#             "autostar": self.autostar,
#         }
#
#     @classmethod
#     def from_json(cls, data: dict):
#         colour = "user"
#         selfstar = False
#         autostar = False
#         if "autostar" in data:
#             autostar = data["autostar"]
#         if "selfstar" in data:
#             selfstar = data["selfstar"]
#         if "colour" in data:
#             colour = data["colour"]
#         messages = []
#         if "messages" in data:
#             messages = [StarboardMessage.from_json(m) for m in data["messages"]]
#         return cls(
#             name=data["name"],
#             channel=data["channel"],
#             emoji=data["emoji"],
#             colour=colour,
#             enabled=data["enabled"],
#             selfstar=selfstar,
#             blacklist_role=data["blacklist_role"],
#             whitelist_role=data["whitelist_role"],
#             messages=messages,
#             blacklist_channel=data["blacklist_channel"],
#             whitelist_channel=data["whitelist_channel"],
#             threshold=data["threshold"],
#             autostar=autostar,
#         )



def setup(bot):
    log.info("[Cog] Starboard")
    bot.add_cog(Starboard(bot))
