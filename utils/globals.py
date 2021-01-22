import logging
import random
import time
import traceback
from typing import Dict

import discord
import motor.motor_asyncio
from discord import VerificationLevel
from discord import VoiceRegion
from discord.ext import commands
from environs import Env

from models.starboard_entry import StarboardEntry

env = Env()
env.read_env()

PREFIX = env('PREFIX')
TOKEN = env('TOKEN')
COGS = env('COGS')
COGS_ECONOMY = env('COGSECONOMY')
COGS_ADMIN = env('COGSADMIN')
COGS_EVENTS = env('COGSEVENTS')
OWNER = int(env('OWNER'))
MONGODB = env('MONGODB')

MDB = motor.motor_asyncio.AsyncIOMotorClient(MONGODB)['discordCrawler']

BOT = 574554734187380756
PM_TRUE = True

CHANNEL = []
PREFIXES = []
REPORTERS = []
STAFF = []
TERMS = []
REACTION_ROLES = []
STARBOARDS: Dict[int, Dict[str, StarboardEntry]] = {}
RECORDERS: Dict[int, discord.Message] = {}


def load_channels(channel_db):
    channel = {}
    for i in channel_db:
        channel[int(i['channel'])] = i['type']
    return channel


def load_prefixes(prefixes_db):
    prefixes = {}
    for i in prefixes_db:
        prefixes[str(i['guild'])] = str(i['prefix'])
    return prefixes


def load_reaction_roles(reaction_roles_db):
    reaction_role = {}
    for i in reaction_roles_db:
        key = int(i['messageId'])
        if key not in reaction_role:
            reaction_role[key] = []
        reaction_role[key].append((i['roleId'], i['emoji']))
    return reaction_role


def load_starboards(starboards_db) -> Dict[int, Dict[str, StarboardEntry]]:
    starboards = {}
    for all_data in starboards_db:
        key = int(all_data['guild'])
        if key not in starboards:
            starboards[key] = {}
        for name, data in all_data['starboards'].items():
            starboard = StarboardEntry.from_json(data)
            starboards[key][name] = starboard
    return starboards


CLEANER = [496672117384019969, 280892074247716864, 790322087981744128]


def check_permission(ctx, permission):
    if ctx.guild is None:
        return True
    if permission == "mm":
        return ctx.guild.me.guild_permissions.manage_messages
    if permission == "mw":
        return ctx.guild.me.guild_permissions.manage_webhooks
    if permission == "af":
        return ctx.guild.me.guild_permissions.attach_files
    if permission == "ar":
        return ctx.guild.me.guild_permissions.add_reactions
    else:
        return False


def is_in_guild(guild_id):
    async def predicate(ctx):
        return ctx.guild and ctx.guild.id == guild_id

    return commands.check(predicate)


def is_staff():
    async def predicate(ctx):
        return global_allowed(ctx)

    return commands.check(predicate)


def is_staff_bool(ctx):
    return global_allowed(ctx)


def global_allowed(ctx):
    global allowed
    if isinstance(ctx.author, discord.Member):
        if ctx.author.roles is not None:
            for r in ctx.author.roles:
                if r.id in STAFF:
                    allowed = True
                    break
                else:
                    allowed = False

            if ctx.author.id == OWNER or ctx.author.id == ctx.guild.owner_id:
                allowed = True
        else:
            allowed = False
    else:
        try:
            if ctx.author.id == OWNER or ctx.author.id == ctx.guild.owner_id:
                allowed = True
            else:
                allowed = False
        except (ValueError, Exception):
            logging.error(traceback.format_exc())
            allowed = False
    try:
        if ctx.guild.get_member(ctx.author.id).guild_permissions.administrator:
            allowed = True
    except (ValueError, Exception):
        logging.error(traceback.format_exc())
        pass
    return allowed


def is_cleaner():
    async def predicate(ctx):
        if isinstance(ctx.author, discord.Member):
            if ctx.author.roles is not None:
                for r in ctx.author.roles:
                    if r.id in CLEANER:
                        return True
                return False
            return False
        return False

    return commands.check(predicate)


def cut_string_in_pieces(inp):
    n = 900
    output = [inp[i:i + n] for i in range(0, len(inp), n)]
    return output


def cut_list_in_pieces(inp):
    n = 30
    output = [inp[i:i + n] for i in range(0, len(inp), n)]
    return output


def count_channels(channels):
    channel_count = 0
    voice_count = 0
    for x in channels:
        if type(x) is discord.TextChannel:
            channel_count += 1
        elif type(x) is discord.VoiceChannel:
            voice_count += 1
        else:
            pass
    return channel_count, voice_count


def get_server_prefix(self, msg):
    return self.get_prefix(self, msg)[-1]


V_LEVELS = {VerificationLevel.none: "None", VerificationLevel.low: "Low", VerificationLevel.medium: "Medium",
            VerificationLevel.high: "(╯°□°）╯︵  ┻━┻", VerificationLevel.extreme: "┻━┻ミヽ(ಠ益ಠ)ノ彡┻━┻"}
REGION = {VoiceRegion.brazil: ":flag_br: Brazil",
          VoiceRegion.eu_central: ":flag_eu: Central Europe",
          VoiceRegion.singapore: ":flag_sg: Singapore",
          VoiceRegion.us_central: ":flag_us: U.S. Central",
          VoiceRegion.sydney: ":flag_au: Sydney",
          VoiceRegion.us_east: ":flag_us: U.S. East",
          VoiceRegion.us_south: ":flag_us: U.S. South",
          VoiceRegion.us_west: ":flag_us: U.S. West",
          VoiceRegion.eu_west: ":flag_eu: Western Europe",
          VoiceRegion.vip_us_east: ":flag_us: VIP U.S. East",
          VoiceRegion.vip_us_west: ":flag_us: VIP U.S. West",
          VoiceRegion.vip_amsterdam: ":flag_nl: VIP Amsterdam",
          VoiceRegion.london: ":flag_gb: London",
          VoiceRegion.amsterdam: ":flag_nl: Amsterdam",
          VoiceRegion.frankfurt: ":flag_de: Frankfurt",
          VoiceRegion.hongkong: ":flag_hk: Hong Kong",
          VoiceRegion.russia: ":flag_ru: Russia",
          VoiceRegion.japan: ":flag_jp: Japan",
          VoiceRegion.southafrica: ":flag_za:  South Africa"}


def check_days(date):
    now = date.fromtimestamp(time.time())
    diff = now - date
    days = diff.days
    return f"{days} {'day' if days == 1 else 'days'} ago"


async def reload_reaction_roles():
    reaction_roles_db = await MDB['reactionroles'].find({}).to_list(length=None)
    return load_reaction_roles(reaction_roles_db)


async def reload_starboards():
    starboards_db = await MDB['starboards'].find({}).to_list(length=None)
    return load_starboards(starboards_db)


class EmbedWithAuthor(discord.Embed):
    """An embed with author image and nickname set."""

    def __init__(self, ctx, **kwargs):
        super(EmbedWithAuthor, self).__init__(**kwargs)
        self.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar_url)
        self.colour = random.randint(0, 0xffffff)
