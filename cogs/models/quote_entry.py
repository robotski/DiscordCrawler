from datetime import datetime
from enum import IntEnum
from typing import Union, List

import discord
from discord import Colour


class QuoteType(IntEnum):
    OLD = 0  # Yellow
    NEW = 1  # Blue


class QuoteModel:
    def __init__(self, quote_id: int, quote_type: QuoteType, message: List[str], date: datetime,
                 author: List[Union[int, str]], submitter: int, jump_url: discord.Message.jump_url = None):
        self.quoteId = quote_id
        self.quoteType = quote_type
        self.message = message
        self.date = date
        self.author = author
        self.submitter = submitter
        self.jump_url = jump_url

    @classmethod
    def from_data(cls, data):
        return cls(data['quoteId'], data['quoteType'], data['message'], data['date'], data['author'], data['submitter'],
                   data['jump_url'])

    def to_dict(self):
        return {
            'quoteId': self.quoteId,
            'quoteType': self.quoteType,
            'message': self.message,
            'date': self.date,
            'author': self.author,
            'submitter': self.submitter,
            'jump_url': self.jump_url
        }


async def get_quote_embed(ctx, quote: QuoteModel):
    embed = discord.Embed(description="")
    await ctx.guild.chunk()
    submitter = await ctx.guild.fetch_member(quote.submitter)

    if quote.quoteType == QuoteType.OLD:
        embed.colour = Colour.gold()

    elif quote.quoteType == QuoteType.NEW:
        embed.colour = Colour.blue()

    for i in range(len(quote.message)):
        author = quote.author[i]
        message = quote.message[i]
        jump_url = quote.jump_url[i]
        if message == "":
            continue
        if author is None:
            embed.add_field(name='\u200b', value=f"{message}", inline=False)
        else:
            if isinstance(author, int):
                author = ctx.guild.get_member(author).display_name
            if jump_url is None:
                embed.add_field(name=f"{author}:", value=f"{message}", inline=False)
            else:
                embed.add_field(name=f"{author}:", value=f"{message}\n[Link]({jump_url})", inline=False)

    embed.set_footer(text=f"Quote ID: {quote.quoteId} - Added by {submitter.display_name}")
    embed.timestamp = quote.date
    return embed


async def get_quote_author_embed(ctx, quote: QuoteModel):
    embed = discord.Embed()
    await ctx.guild.chunk()
    submitter = await ctx.guild.fetch_member(quote.submitter)

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
