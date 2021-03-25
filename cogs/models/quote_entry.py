from datetime import datetime
from enum import IntEnum
from typing import List

import discord
from discord import Colour
from discord.ext import commands


class QuoteType(IntEnum):
    OLD = 0  # Yellow
    NEW = 1  # Blue


class QuoteModel:
    def __init__(self, quote_id: int, quote_type: QuoteType, message: List[str], date: datetime, author_id: List[int],
                 author_name: List[str], submitter_id: int, submitter_name: str,
                 jump_url: discord.Message.jump_url = None):
        self.quoteId = quote_id
        self.quoteType = quote_type
        self.message = message
        self.date = date
        self.author_id = author_id
        self.author_name = author_name
        self.submitter_id = submitter_id
        self.submitter_name = submitter_name
        self.jump_url = jump_url

    @classmethod
    def from_data(cls, data):
        return cls(data['quoteId'], data['quoteType'], data['message'], data['date'], data['author_id'],
                   data['author_name'], data['submitter_id'], data['submitter_name'], data['jump_url'])

    def to_dict(self):
        return {
            'quoteId': self.quoteId,
            'quoteType': self.quoteType,
            'message': self.message,
            'date': self.date,
            'author_id': self.author_id,
            'author_name': self.author_name,
            'submitter_id': self.submitter_id,
            'submitter_name': self.submitter_name,
            'jump_url': self.jump_url
        }


async def get_quote_embed(bot: commands.Bot, ctx, quote: QuoteModel):
    embed = discord.Embed(description="")
    await ctx.guild.chunk()
    submitter = bot.get_user(quote.submitter_id)
    # submitter = await ctx.guild.fetch_member(quote.submitter_id)

    if submitter is None:
        submitter = quote.submitter_name
    else:
        submitter = submitter.display_name

    if quote.quoteType == QuoteType.OLD:
        embed.colour = Colour.gold()

    elif quote.quoteType == QuoteType.NEW:
        embed.colour = Colour.blue()

    for i in range(len(quote.message)):
        if quote.author_id[i] is not None:
            author = ctx.guild.get_member(quote.author_id[i])
            if author is None:
                author = quote.author_name[i]
            else:
                author = author.display_name
        else:
            author = quote.author_name[i]
        message = quote.message[i]
        jump_url = quote.jump_url[i]
        if message == "":
            continue
        if author is None:
            embed.add_field(name='\u200b', value=f"{message}", inline=False)
        else:
            # if isinstance(author, int):
            #     author = ctx.guild.get_member(author).display_name
            if jump_url is None:
                embed.add_field(name=f"{author}:", value=f"{message}", inline=False)
            else:
                embed.add_field(name=f"{author}:", value=f"{message}\n[Link]({jump_url})", inline=False)

    embed.set_footer(text=f"Quote ID: {quote.quoteId} - Added by {submitter}")
    embed.timestamp = quote.date
    return embed


async def get_quote_author_embed(ctx, quote: QuoteModel):
    embed = discord.Embed()
    await ctx.guild.chunk()
    submitter = await ctx.guild.fetch_member(quote.submitter_id)

    embed.title = "You have been "
    embed.description = f"The following message as included:\n\n``{quote.message}``\n\n"
    if quote.quoteType == QuoteType.NEW:
        embed.colour = Colour.gold()
        embed.title = f"Warned on"
        embed.description += "Warnings don't mean the end of the world. They are used to track potential " \
                             "rule-breakers and to keep record for the complete staff team."

    embed.title += f" {ctx.guild.name}"
    embed.set_footer(text=f"Quote ID: {quote.quoteId} - Added by {submitter.display_name}")
    embed.timestamp = quote.date
    return embed
