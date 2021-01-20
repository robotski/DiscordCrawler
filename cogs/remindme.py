import asyncio
import datetime

import discord
import time

import utils.globals as GG
from discord.ext import commands
from utils import logger

log = logger.logger


class RemindMe(commands.Cog):
    def __init__(self, bot: discord.ext.commands.Bot):
        self.bot = bot
        self.units = {"minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 2592000}

    @commands.command()
    async def remindme(self, ctx: commands.Context, quantity: int, time_unit: str, *, text: str):
        time_unit = time_unit.lower()
        author = ctx.author
        s = ""
        if time_unit.endswith("s"):
            time_unit = time_unit[:-1]
            s = "s"
        if not time_unit in self.units:
            await ctx.send("Invalid time unit. Choose minutes/hours/days/weeks/month")
            return
        if quantity < 1:
            await ctx.send("Quantity must not be 0 or negative.")
            return
        if len(text) > 1960:
            await ctx.send("Text is too long.")
            return
        seconds = self.units[time_unit] * quantity
        future = int(time.time()+seconds)
        await GG.MDB['reminders'].insert_one({'ID': author.id, 'FUTURE': future, 'TEXT': text})
        log.info("{} ({}) set a reminder.".format(author.name, author.id))
        await ctx.send("I will remind you that in {} {}.".format(str(quantity), time_unit + s))
        # await asyncio.sleep(5)

    @commands.command()
    async def forgetme(self, ctx: discord.ext.commands.Context):
        author = ctx.author
        result = await GG.MDB['reminders'].delete_many({'ID': author.id})
        if result.deleted_count:
            await ctx.send("All your notifications have been removed.")
        else:
            await ctx.send("You don't have any upcoming notification.")
        # await asyncio.sleep(5)

    async def check_reminders(self):
        while self is self.bot.get_cog("RemindMe"):
            for reminder in await GG.MDB['reminders'].find({'FUTURE': {'$lte': int(time.time())}}).to_list(length=None):
                try:
                    await self.bot.wait_until_ready()
                    dm_channel = await self.bot.get_user(reminder['ID']).create_dm()
                    await dm_channel.send("You asked me to remind you this:\n{}".format(reminder['TEXT']))
                except (discord.Forbidden, discord.NotFound):
                    await GG.MDB['reminders'].delete_one(reminder)
                else:
                    await GG.MDB['reminders'].delete_one(reminder)
            await asyncio.sleep(5)


def setup(bot):
    log.info("[Cog] RemindMe")
    n = RemindMe(bot)
    loop = asyncio.get_event_loop()
    loop.set_debug(enabled=True)
    loop.create_task(n.check_reminders())
    bot.add_cog(n)
