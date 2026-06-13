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
    "cogs.voice_fun",
]

# comandos liberados fora do !floq (configuração de servidor / admin)
ADMIN_ALLOWED_COMMANDS = {
    "setchannel",
    "guildcreate",
    "guildjoin",
    "guildranking",
    "shoprefresh",
}

# o próprio ponto de entrada
ENTRYPOINT_COMMANDS = {"floq"}


class GameNotStartedError(commands.CheckFailure):
    pass


class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=BOT_PREFIX, intents=intents)
        self.logger = logger
        self.add_check(self._global_gate)

    async def _global_gate(self, ctx: commands.Context) -> bool:
        """Bloqueia tudo, exceto !floq e comandos de configuração de admin."""
        if ctx.command is None:
            return True
        name = ctx.command.name
        if name in ENTRYPOINT_COMMANDS or name in ADMIN_ALLOWED_COMMANDS:
            return True
        raise GameNotStartedError()

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
        await self.change_presence(activity=discord.Game(name="!floq | Floq"))

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, GameNotStartedError):
            await ctx.send(
                f"🎮 {ctx.author.mention}, comece com **`!floq`** para abrir o console do Floq! "
                "Todas as ações acontecem por lá. 🐾"
            )
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`")
            return
        if isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need more permissions to do that.")
            return
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"🐾 Floq está descansando! Tenta de novo em **{error.retry_after:.0f}s**."
            )
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ Você não tem permissão para usar este comando.")
            return
        if isinstance(error, commands.BadArgument):
            await ctx.send("❌ Argumento inválido. Confira o formato do comando.")
            return
        logger.error(f"Command error in {ctx.command}: {error}", exc_info=True)
        await ctx.send("❌ An unexpected error occurred.")

    async def close(self):
        logger.info("Bot shutting down...")
        await super().close()
