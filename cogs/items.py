# cogs/items.py
import discord
from discord.ext import commands
import db
import item_manager

class Items(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx, page: int = 1):
        user_id = str(ctx.author.id)
        total = db.count_user_items(user_id)
        if total == 0:
            await ctx.send("Seu inventário está vazio. Use `!shop` para comprar itens.")
            return
        per_page = 10
        items = db.get_user_items(user_id, page, per_page)
        if not items and page > 1:
            await ctx.send(f"Página {page} não existe.")
            return
        embed = discord.Embed(title="🎒 Inventário", color=discord.Color.blue())
        for it in items:
            rarity_emoji = {"common":"⚪", "uncommon":"🟢", "rare":"🔵", "epic":"🟣", "legendary":"🟡"}.get(it["rarity"], "⚪")
            embed.add_field(
                name=f"{rarity_emoji} {it['name']} x{it['quantity']}",
                value=f"Tipo: {it['type']} | Slot: {it['slot'] or 'nenhum'}",
                inline=False
            )
        total_pages = max(1, (total + per_page - 1) // per_page)
        embed.set_footer(text=f"Página {page}/{total_pages} • Use !equip <id>")
        await ctx.send(embed=embed)

    @commands.command(name="equip")
    async def equip(self, ctx, item_id: int):
        user_id = str(ctx.author.id)
        item = item_manager.get_item(item_id)
        if not item:
            await ctx.send("❌ ID de item inválido.")
            return
        if not item.get("slot"):
            await ctx.send("❌ Este item não pode ser equipado (não tem slot definido).")
            return
        success = db.equip_item(user_id, item_id)
        if success:
            await ctx.send(f"✅ Equipou **{item['name']}** no slot **{item['slot']}**.")
        else:
            await ctx.send("❌ Você não possui este item ou algo deu errado.")

    @commands.command(name="unequip")
    async def unequip(self, ctx, slot: str):
        user_id = str(ctx.author.id)
        db.unequip_item(user_id, slot.lower())
        await ctx.send(f"✅ Removeu o item do slot **{slot}**.")

    @commands.command(name="equipped")
    async def equipped(self, ctx):
        user_id = str(ctx.author.id)
        items = db.get_equipped_items(user_id)
        if not items:
            await ctx.send("Você não tem nada equipado.")
            return
        embed = discord.Embed(title="⚔️ Equipamentos Atuais", color=discord.Color.gold())
        for it in items:
            embed.add_field(name=it["slot"].capitalize(), value=f"{it['name']} ({it['rarity']})", inline=True)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Items(bot))
