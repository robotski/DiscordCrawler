import asyncio
import random
import traceback
from os import listdir
from os.path import isfile, join

import discord
from discord.ext import commands

import utils.globals as GG
from cogs.models.quote_entry import QuoteModel
from utils import logger

log = logger.logger

version = "v2.0.2"
SHARD_COUNT = 1
TESTING = False
defaultPrefix = GG.PREFIX if not TESTING else '='
intents = discord.Intents().all()


def get_prefix(b, message):
    if not message.guild:
        return commands.when_mentioned_or(defaultPrefix)(b, message)

    gp = ['-', b.prefixes.get(str(message.guild.id), defaultPrefix)]
    return commands.when_mentioned_or(*gp)(b, message)


class Crawler(commands.AutoShardedBot):
    def __init__(self, prefix, help_command=None, description=None, **options):
        super(Crawler, self).__init__(prefix, help_command, description, **options)
        self.version = version
        self.owner = None
        self.testing = TESTING
        self.token = GG.TOKEN
        self.mdb = GG.MDB
        self.prefixes = GG.PREFIXES

        self.bg_task = self.loop.create_task(self.name_change())

    async def name_change(self):
        await self.wait_until_ready()
        while not self.is_closed():
            total_members = sum(len(s.members) for s in self.guilds)
            quote = QuoteModel.from_data(
                [d async for d in GG.MDB.quote.aggregate([{'$sample': {'size': 1}}])][0]).message
            await bot.change_presence(activity=discord.Game(f"{random.choice(quote)}"), afk=True)
            await asyncio.sleep(total_members + 200)
            await bot.change_presence(activity=discord.Game(f"with {len(bot.guilds)} servers | =help | {version}"),
                                      afk=True)
            await asyncio.sleep(total_members + 200)

    def get_server_prefix(self, msg):
        return get_prefix(self, msg)[-1]

    async def launch_shards(self):
        if self.shard_count is None:
            recommended_shards, _ = await self.http.get_bot_gateway()
            if recommended_shards >= 96 and not recommended_shards % 16:
                # half, round up to nearest 16
                self.shard_count = recommended_shards // 2 + (16 - (recommended_shards // 2) % 16)
            else:
                self.shard_count = recommended_shards // 2
        log.info(f"Launching {self.shard_count} shards!")
        await super(Crawler, self).launch_shards()


bot = Crawler(prefix=get_prefix, intents=intents, case_insensitive=True, status=discord.Status.idle,
              description="A bot.", shard_count=SHARD_COUNT, testing=TESTING,
              activity=discord.Game(f"=help | {version}"),
              help_command=commands.DefaultHelpCommand(command_attrs={"name": "oldhelp"}))


@bot.event
async def on_message(msg):
    if not msg.author.bot:
        await bot.invoke(await bot.get_context(msg))


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(f"with {len(bot.guilds)} servers | =help | {version}"), afk=True)
    print(f"Logged in as {bot.user.name} ({bot.user.id})")


@bot.event
async def on_connect():
    await fillGlobals()
    bot.owner = await bot.fetch_user(GG.OWNER)
    print(f"OWNER: {bot.owner.name}")


@bot.event
async def on_resumed():
    log.info('resumed.')


async def fillGlobals():
    log.info("Filling Globals")
    prefixes_db = await GG.MDB['prefixes'].find({}).to_list(length=None)
    GG.PREFIXES = GG.load_prefixes(prefixes_db)
    bot.prefixes = GG.PREFIXES

    channel_db = await GG.MDB['channelinfo'].find({}).to_list(length=None)
    GG.CHANNEL = GG.load_channels(channel_db)

    reporters_db = await GG.MDB['reports'].find({}).to_list(length=None)
    GG.REPORTERS = [int(i['message']) for i in reporters_db]

    staff_db = await GG.MDB['serverstaff'].find({}).to_list(length=None)
    GG.STAFF = [int(i['roles']) for i in staff_db]

    reaction_roles_db = await GG.MDB['reactionroles'].find({}).to_list(length=None)
    GG.REACTION_ROLES = GG.load_reaction_roles(reaction_roles_db)

    starboard_db = await GG.MDB['starboards'].find({}).to_list(length=None)
    GG.STARBOARDS = GG.load_starboards(starboard_db)

    log.info("Finished Filling Globals")


def loader(cog):
    global extension, e
    for extension in [f.replace('.py', '') for f in listdir(cog) if isfile(join(cog, f))]:
        try:
            bot.load_extension(cog + "." + extension)
        except (ValueError, Exception) as e:
            log.error(f'Failed to load extension {extension}')
            log.error(traceback.format_exc())


if __name__ == "__main__":
    bot.state = "run"
    loader(GG.COGS)
    loader(GG.COGS_ECONOMY)
    loader(GG.COGS_ADMIN)
    loader(GG.COGS_EVENTS)
    bot.run(bot.token)
