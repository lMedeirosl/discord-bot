# cogs/guilds.py
"""
Sistema de Guildas (alianças entre servidores)
------------------------------------------------
Permite que servidores se unam em guildas (até 4 servidores) e comparem
o poder combinado de seus mascotes Floq.

Comandos:
  !guildcreate <nome>   – cria uma nova guilda com este servidor
  !guildjoin <nome>     – entra em uma guilda existente
  !guildinfo            – mostra a guilda do servidor atual
  !guildranking         – ranking de guildas por poder total
  !poder                – mostra o poder atual do Floq deste servidor
"""

import discord
from discord.ext import commands
import db


class Guilds(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="poder", aliases=["power"])
    async def power(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            await ctx.send("🐾 Esse comando só funciona dentro de um servidor!")
            return
        server_id = str(ctx.guild.id)
        db.ensure_server(server_id)
        power = db.get_power(server_id)
        mascot = db.get_mascot(server_id)

        embed = discord.Embed(
            title="💪 Poder do Floq",
            description=(
                f"Floq deste servidor está nível **{mascot['level']}**, "
                f"com **{mascot['happiness']}%** de felicidade.\n"
                f"⚡ **Poder total: {power}**"
            ),
            color=discord.Color.dark_orange(),
        )
        embed.set_footer(text="Poder = nível×10 + felicidade + bônus de equipamentos")
        await ctx.send(embed=embed)

    @commands.command(name="guildcreate")
    @commands.has_permissions(manage_guild=True)
    async def guild_create(self, ctx: commands.Context, *, name: str) -> None:
        if not ctx.guild:
            await ctx.send("🐾 Esse comando só funciona dentro de um servidor!")
            return
        if len(name) > 32:
            await ctx.send("❌ O nome da guilda pode ter no máximo 32 caracteres.")
            return

        server_id = str(ctx.guild.id)
        db.ensure_server(server_id)

        guild_id = db.create_guild(name, server_id)
        if guild_id is None:
            existing = db.get_server_guild(server_id)
            if existing:
                embed = discord.Embed(
                    title="❌ Já faz parte de uma guilda",
                    description=(
                        f"Esse servidor já pertence à guilda **{existing['name']}**.\n"
                        f"Não é possível criar outra."
                    ),
                    color=discord.Color.red(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Nome indisponível",
                    description=f"Já existe uma guilda chamada **{name}**. Escolha outro nome.",
                    color=discord.Color.red(),
                )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🏰 Guilda fundada!",
            description=(
                f"🐾 Floq abanou o rabo MUITO forte! A guilda **{name}** foi criada!\n"
                f"Outros servidores podem entrar com `!guildjoin {name}` (máx. 4 servidores)."
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"ID da guilda: {guild_id}")
        await ctx.send(embed=embed)

    @commands.command(name="guildjoin")
    @commands.has_permissions(manage_guild=True)
    async def guild_join(self, ctx: commands.Context, *, name: str) -> None:
        if not ctx.guild:
            await ctx.send("🐾 Esse comando só funciona dentro de um servidor!")
            return

        server_id = str(ctx.guild.id)
        db.ensure_server(server_id)

        target = db.get_guild_by_name(name)
        if target is None:
            await ctx.send(f"❌ Nenhuma guilda encontrada com o nome **{name}**.")
            return

        success = db.join_guild(target["id"], server_id)
        if not success:
            existing = db.get_server_guild(server_id)
            if existing:
                embed = discord.Embed(
                    title="❌ Já faz parte de uma guilda",
                    description=f"Esse servidor já pertence à guilda **{existing['name']}**.",
                    color=discord.Color.red(),
                )
            else:
                embed = discord.Embed(
                    title="❌ Guilda cheia",
                    description=f"A guilda **{name}** já tem o máximo de 4 servidores.",
                    color=discord.Color.red(),
                )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🏰 Guilda conquistada!",
            description=(
                f"🐾 Esse servidor agora faz parte da guilda **{name}**!\n"
                f"Use `!guildinfo` para ver os detalhes da aliança."
            ),
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="guildinfo")
    async def guild_info(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            await ctx.send("🐾 Esse comando só funciona dentro de um servidor!")
            return

        server_id = str(ctx.guild.id)
        guild = db.get_server_guild(server_id)
        if guild is None:
            embed = discord.Embed(
                title="🏰 Sem guilda",
                description=(
                    "Esse servidor ainda não faz parte de nenhuma guilda.\n"
                    "Use `!guildcreate <nome>` para fundar uma, ou `!guildjoin <nome>` "
                    "para entrar em uma existente."
                ),
                color=discord.Color.light_grey(),
            )
            await ctx.send(embed=embed)
            return

        members = db.get_guild_members(guild["id"])
        total_power = db.get_guild_power(guild["id"])

        embed = discord.Embed(
            title=f"🏰 Guilda {guild['name']}",
            description=f"⚡ **Poder total da aliança: {total_power}**",
            color=discord.Color.purple(),
        )

        for m in members:
            member_guild = self.bot.get_guild(int(m["server_id"]))
            server_name = member_guild.name if member_guild else f"Servidor #{m['server_id']}"
            server_power = db.get_power(m["server_id"])
            mascot = db.get_mascot(m["server_id"])
            tag = " 👑 (este servidor)" if m["server_id"] == server_id else ""
            embed.add_field(
                name=f"🐾 {server_name}{tag}",
                value=f"Lv.{mascot['level']} · {mascot['happiness']}% felicidade · ⚡{server_power}",
                inline=False,
            )

        embed.set_footer(text=f"{len(members)}/4 servidores na aliança")
        await ctx.send(embed=embed)

    @commands.command(name="guildranking", aliases=["guildrank"])
    async def guild_ranking(self, ctx: commands.Context) -> None:
        guilds = db.get_all_guilds_ranked()

        if not guilds:
            embed = discord.Embed(
                title="🏆 Ranking de Guildas",
                description="Nenhuma guilda foi criada ainda. Seja o primeiro com `!guildcreate <nome>`!",
                color=discord.Color.light_grey(),
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🏆 Ranking de Guildas",
            description="As alianças mais poderosas entre os servidores do Floq:",
            color=discord.Color.gold(),
        )

        medals = ["🥇", "🥈", "🥉"]
        for i, g in enumerate(guilds[:10]):
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            embed.add_field(
                name=f"{medal} {g['name']}",
                value=f"⚡ Poder total: **{g['total_power']}**  •  {g['member_count']} servidor(es)",
                inline=False,
            )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Guilds(bot))
