# bot.py
import discord
from discord.ext import commands
import logging
import os
from config import BOT_PREFIX
import db
import item_manager

logger = logging.getLogger(__name__)

COGS = [
    "cogs.economy",
    "cogs.mascot",
    "cogs.items",
    "cogs.floq_events",
    "cogs.guilds",
    "cogs.gameboy",
]

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=BOT_PREFIX, intents=intents)
        self.logger = logger

    async def setup_hook(self):
        db.initialize_database()
        item_manager.load_all_items()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}", exc_info=True)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="!pet | Floq"))

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`")
            return
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need more permissions to do that.")
            return
        logger.error(f"Command error in {ctx.command}: {error}")
        await ctx.send("❌ An unexpected error occurred.")

    async def close(self):
        logger.info("Bot shutting down...")
        await super().close()
