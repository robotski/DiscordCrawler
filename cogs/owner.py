import asyncio
import datetime
import os
import subprocess
import inspect
from os.path import isfile, join

import discord

from DBService import DBService
import utils.globals as GG
from discord import Permissions
from discord.ext import commands
from utils import logger

log = logger.logger

extensions = [x.replace('.py', '') for x in os.listdir(GG.COGS) if x.endswith('.py')]
extensions5e = [x.replace('.py', '') for x in os.listdir(GG.COGS) if x.endswith('.py')]
path = GG.COGS + '.'
path5e = GG.COGS + '.'


class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @GG.is_owner()
    async def mute(self, ctx, id):
        member = await ctx.guild.fetch_member(id)
        guildChannels = member.guild.text_channels
        overwrite = discord.PermissionOverwrite()
        overwrite.send_messages = False
        for x in guildChannels:
            await x.set_permissions(member, overwrite=overwrite)
            # print(f"SEND in {x}: {x.permissions_for(member).send_messages}")

    @commands.command()
    @GG.is_owner()
    async def unmute(self, ctx, id):
        member = await ctx.guild.fetch_member(id)
        guildChannels = member.guild.text_channels
        for x in guildChannels:
            await x.set_permissions(member, overwrite=None)

    @commands.command(hidden=True)
    @GG.is_owner()
    async def gitpull(self, ctx):
        """Pulls from github and updates bot"""
        await ctx.trigger_typing()
        await ctx.send(f"```{subprocess.run('git pull', stdout=subprocess.PIPE, shell=True).stdout.decode('utf-8')}```")
        for cog in extensions:
            ctx.bot.unload_extension(f'{path}{cog}')
        for cog in extensions:
            members = inspect.getmembers(cog)
            for name, member in members:
                if name.startswith('on_'):
                    ctx.bot.add_listener(member, name)
            try:
                ctx.bot.load_extension(f'{path}{cog}')
            except Exception as e:
                await ctx.send(f'LoadError: {cog}\n{type(e).__name__}: {e}')
        await ctx.send('All cogs reloaded :white_check_mark:')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def presenceLite(self, ctx):
        msqQueue = []
        msg = '```js\n'
        msg += '{!s:19s} | {!s:>8s} | {} | {}\n'.format('ID', 'Member', 'Name', 'Owner')
        for guild in self.bot.guilds:
            msg += '{!s:19s} | {!s:>8s}| {} | {}\n'.format(guild.id, guild.member_count, guild.name, guild.owner)
            if len(msg) > 900:
                msg += '```'
                msqQueue.append(msg)
                msg = '```js\n'
                msg += '{!s:19s} | {!s:>8s} | {} | {}\n'.format('ID', 'Member', 'Name', 'Owner')
        msg += '```'
        if len(msqQueue) > 0:
            for x in msqQueue:
                await ctx.send(x)
        else:
            await ctx.send(msg)

    @commands.command(hidden=True, rest_is_raw=True)
    @commands.is_owner()
    async def exec(self, ctx, TYPE: str, *, arg):
        response = "You can only use ``one``, ``all``, or ``command``"
        try:
            if TYPE == "one":
                response = DBService.exec(arg).fetchone()
            if TYPE == "all":
                response = DBService.exec(arg).fetchall()
            if TYPE == "command":
                response = DBService.exec(arg)
        except Exception as e:
            response = e
        await ctx.send(response)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def checkglobal(self, ctx, GLOBAL: str):
        if GLOBAL == "PREFIXES":
            await ctx.send(GG.PREFIXES)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def load(self, ctx, extension_name: str):
        """[OWNER ONLY]"""
        if ctx.author.id == GG.OWNER:
            try:
                ctx.bot.load_extension(GG.COGS + "." + extension_name)
            except (AttributeError, ImportError) as e:
                await ctx.send("```py\n{}: {}\n```".format(type(e).__name__, str(e)))
                return
            await ctx.send("{} loaded".format(extension_name))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unload(self, ctx, extension_name: str):
        """[OWNER ONLY]"""
        if ctx.author.id == GG.OWNER:
            ctx.bot.unload_extension(GG.COGS + "." + extension_name)
            await ctx.send("{} unloaded".format(extension_name))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def checkglobal(self, ctx, GLOBAL: str):
        if GLOBAL == "REACTION":
            await ctx.send(GG.REACTIONROLES)

def setup(bot):
    log.info("Loading Owner Cog...")
    bot.add_cog(Owner(bot))
