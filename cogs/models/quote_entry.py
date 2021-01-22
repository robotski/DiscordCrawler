from datetime import datetime
from typing import Union, List

import discord
from discord import Colour

from enum import IntEnum


class QuoteType(IntEnum):
    OLD = 0  # Blue
    NEW = 1  # Yellow


class QuoteModel:
    def __init__(self, quoteId: int, quoteType: QuoteType, message: List[str], date: datetime, author: List[Union[int, str]], submitter: int):
        self.quoteId = quoteId
        self.quoteType = quoteType
        self.message = message
        self.date = date
        self.author = author
        self.submitter = submitter

    @classmethod
    def from_data(cls, data):
        return cls(data['quoteId'], data['quoteType'], data['message'], data['date'], data['author'], data['submitter'])

    def to_dict(self):
        return {
            'quoteId': self.quoteId,
            'quoteType': self.quoteType,
            'message': self.message,
            'date': self.date,
            'author': self.author,
            'submitter': self.submitter
        }


async def getQuoteEmbed(ctx, quote: QuoteModel):
    embed = discord.Embed(description="")
    # embed = discord.Embed()
    await ctx.guild.chunk()
    submitter = await ctx.guild.fetch_member(quote.submitter)
    # author = await ctx.guild.fetch_member(quote.author)

    if quote.quoteType == QuoteType.OLD:
        embed.colour = Colour.gold()
        # embed.title = f"Old"

    elif quote.quoteType == QuoteType.NEW:
        embed.colour = Colour.blue()
        # embed.title = f"New"

    # embed.title += f" added for {author.display_name}"
    # embed.description = quote.message

    for i in range(len(quote.message)):
        author = quote.author[i]
        message = quote.message[i]
        if message == "":
            continue
        if author is None:
            # embed.description += f"{message}\n"
            embed.add_field(name='\u200b', value=f"{message}", inline=False)
        else:
            if isinstance(author, int):
                author = ctx.guild.get_member(author).display_name
            # embed.description += f"{author}: {message}\n"
            embed.add_field(name=f"{author}:", value=f"{message}", inline=False)

    embed.set_footer(text=f"Quote ID: {quote.quoteId} - Added by {submitter.display_name}")
    embed.timestamp = quote.date
    return embed


async def getQuoteAuthorEmbed(ctx, quote: QuoteModel):
    embed = discord.Embed()
    await ctx.guild.chunk()
    submitter = await ctx.guild.fetch_member(quote.submitter)

    embed.title = "You have been "
    embed.description = f"The following message as included:\n\n``{quote.message}``\n\n"
    if quote.quoteType == QuoteType.NEW:
        embed.colour = Colour.gold()
        embed.title = f"Warned on"
        embed.description += "Warnings don't mean the end of the world. They are used to track potential rule-breakers and to keep record for the complete staff team."

    embed.title += f" {ctx.guild.name}"
    embed.set_footer(text=f"Quote ID: {quote.quoteId} - Added by {submitter.display_name}")
    embed.timestamp = quote.date
    return embed
