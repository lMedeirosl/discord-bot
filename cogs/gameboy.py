# cogs/gameboy.py
"""
🎮 Console Floq — interface estilo Game Boy
---------------------------------------------
Comando !floq abre um "console" com menu de seleção (dropdown) e botões,
navegando entre telas (Pet, Inventário, Equipar, Loja, Banco, Guilda,
Status, Instruções) tudo dentro de embeds com visual retrô.
"""

import time
import random
import discord
from discord.ext import commands
from discord.ui import View, Select, Button, Modal, TextInput
import db
from cogs.mascot import generate_mascot_image, MOOD_LABELS, FEED_COST, FEED_HAPPINESS_MIN, FEED_HAPPINESS_MAX, PLAY_HAPPINESS_BOOST

# paleta clássica Game Boy (verde DMG)
GB_GREEN = discord.Color.from_rgb(155, 188, 15)

RARITY_EMOJI = {
    "common":    "⚪",
    "uncommon":  "🟢",
    "rare":      "🔵",
    "epic":      "🟣",
    "legendary": "🟡",
}

SLOT_EMOJI = {
    "head":      "🎩",
    "body":      "👕",
    "accessory": "📿",
    "weapon":    "🦴",
}


def gb_frame(lines: list[str]) -> str:
    """Monta um 'visor' de Game Boy usando code block."""
    width = 30
    out = ["┌" + "─" * width + "┐"]
    for line in lines:
        out.append("│ " + line.ljust(width - 1) + "│")
    out.append("└" + "─" * width + "┘")
    return "```\n" + "\n".join(out) + "\n```"


# ─────────────────────────────────────────────────────────────────────────
# TELAS
# ─────────────────────────────────────────────────────────────────────────

def screen_home(server_id: str, user_id: str) -> discord.Embed:
    db.ensure_server(server_id)
    db.ensure_user(user_id)
    mascot = db.get_mascot(server_id)
    balance = db.get_balance(user_id)
    mood = db.get_mood(server_id)

    body = [
        " " * 7 + "FLOQ GAME",
        "",
        f"Mascote: {mascot['mascot_name']}",
        f"Nível:   {mascot['level']}",
        f"Humor:   {MOOD_LABELS.get(mood, mood)}",
        f"Carteira: {balance} moedas",
        "",
        "Selecione uma opção",
        "no menu abaixo \u25BC",
    ]
    embed = discord.Embed(
        title="🎮 CONSOLE FLOQ",
        description=gb_frame(body),
        color=GB_GREEN,
    )
    embed.set_footer(text="A: confirmar  •  ▼: menu")
    return embed


def screen_pet(server_id: str, user_id: str):
    mascot = db.get_mascot(server_id)
    mood = db.get_mood(server_id)
    buf = generate_mascot_image(server_id, user_id)
    file = discord.File(buf, filename="mascot.png")

    embed = discord.Embed(
        title="🐾 TELA — PET",
        description=gb_frame([
            f"{mascot['mascot_name']}  Lv.{mascot['level']}",
            f"Humor: {MOOD_LABELS.get(mood, mood)}",
            f"Felicidade: {mascot['happiness']}%",
            "",
            "[Alimentar] [Brincar]",
        ]),
        color=GB_GREEN,
    )
    embed.set_image(url="attachment://mascot.png")
    return embed, file


def screen_inventory(user_id: str, page: int = 1):
    per_page = 6
    total = db.count_user_items(user_id)
    items = db.get_user_items(user_id, page, per_page)

    lines = ["MOCHILA", ""]
    if not items:
        lines.append("(vazia)")
    else:
        for it in items:
            r = RARITY_EMOJI.get(it["rarity"], "⚪")
            slot_txt = f" [{it['slot']}]" if it["slot"] else ""
            lines.append(f"{r} {it['name'][:18]} x{it['quantity']}{slot_txt}")

    total_pages = max(1, (total + per_page - 1) // per_page)
    lines.append("")
    lines.append(f"Página {page}/{total_pages}")

    embed = discord.Embed(
        title="🎒 TELA — MOCHILA",
        description=gb_frame(lines),
        color=GB_GREEN,
    )
    return embed


def screen_equip(user_id: str):
    equipped = db.get_equipped_items(user_id)
    by_slot = {e["slot"]: e for e in equipped}

    lines = ["EQUIPAMENTO", ""]
    for slot in ("head", "body", "accessory", "weapon"):
        emoji = SLOT_EMOJI.get(slot, "•")
        if slot in by_slot:
            it = by_slot[slot]
            r = RARITY_EMOJI.get(it["rarity"], "⚪")
            lines.append(f"{emoji} {slot.capitalize():<10}{r}{it['name'][:13]}")
        else:
            lines.append(f"{emoji} {slot.capitalize():<10}---")
    lines.append("")
    lines.append("Selecione item p/ trocar")

    embed = discord.Embed(
        title="⚔️ TELA — EQUIPAMENTO",
        description=gb_frame(lines),
        color=GB_GREEN,
    )
    return embed


def screen_shop():
    items, rotated_at = db.get_shop_items()
    next_rotation = rotated_at + db.SHOP_ROTATION_HOURS * 3600
    mins_left = max(0, (next_rotation - int(time.time())) // 60)

    lines = ["LOJA DO FLOQ", ""]
    if not items:
        lines.append("(sem itens hoje)")
    else:
        for it in items[:10]:
            r = RARITY_EMOJI.get(it["rarity"], "⚪")
            lines.append(f"{r} {it['name'][:16]:<16}{it['base_price']:>5}")
    lines.append("")
    lines.append(f"Nova seleção em {mins_left} min")

    embed = discord.Embed(
        title="🏪 TELA — LOJA",
        description=gb_frame(lines),
        color=GB_GREEN,
    )
    return embed, items


def screen_bank(server_id: str, user_id: str):
    bank_balance = db.get_server_bank(server_id)
    balance = db.get_balance(user_id)

    lines = [
        "BANCO DO SERVIDOR",
        "",
        f"Cofre:    {bank_balance} moedas",
        f"Carteira: {balance} moedas",
        "",
        "[Depositar] [Sacar]",
    ]
    embed = discord.Embed(
        title="🏦 TELA — BANCO",
        description=gb_frame(lines),
        color=GB_GREEN,
    )
    return embed


def screen_guild(bot: commands.Bot, server_id: str):
    guild = db.get_server_guild(server_id)
    lines = ["GUILDA", ""]
    if guild is None:
        lines.append("Sem guilda.")
        lines.append("")
        lines.append("!guildcreate <nome>")
        lines.append("!guildjoin <nome>")
    else:
        members = db.get_guild_members(guild["id"])
        power = db.get_guild_power(guild["id"])
        lines.append(f"Nome: {guild['name'][:18]}")
        lines.append(f"Poder total: {power}")
        lines.append(f"Servidores: {len(members)}/4")
        lines.append("")
        for m in members[:4]:
            g = bot.get_guild(int(m["server_id"]))
            gname = g.name if g else f"#{m['server_id']}"
            lines.append(f" • {gname[:24]}")

    embed = discord.Embed(
        title="🏰 TELA — GUILDA",
        description=gb_frame(lines),
        color=GB_GREEN,
    )
    return embed


def screen_status(server_id: str, user_id: str):
    mascot = db.get_mascot(server_id)
    power = db.get_power(server_id)
    streak = db.get_daily_streak(user_id)
    adv = db.get_active_adventure(server_id)

    lines = [
        "STATUS",
        "",
        f"Nível:      {mascot['level']}",
        f"Felicidade: {mascot['happiness']}%",
        f"Poder:      {power}",
        f"Streak diário: {streak} dia(s)",
        "",
    ]
    if adv:
        pct = min(100, int(adv["progress"] / adv["goal"] * 100))
        lines.append(f"Aventura: {pct}%")
        lines.append(f"({adv['title'][:20]})")
    else:
        lines.append("Sem aventura ativa")

    embed = discord.Embed(
        title="⚡ TELA — STATUS",
        description=gb_frame(lines),
        color=GB_GREEN,
    )
    return embed


def screen_help():
    lines = [
        "INSTRUÇÕES",
        "",
        "!pet     - ver/cuidar do Floq",
        "!shop    - loja rotativa",
        "!buy <item> - comprar",
        "!inv     - mochila",
        "!equip <id> - equipar",
        "!daily   - recompensa diária",
        "!work    - trabalhar",
        "!banco   - cofre do servidor",
        "!guildinfo - sua guilda",
        "!ajudar  - aventura ativa",
        "",
        "Use !floq p/ abrir o console",
    ]
    embed = discord.Embed(
        title="📖 TELA — INSTRUÇÕES",
        description=gb_frame(lines),
        color=GB_GREEN,
    )
    return embed


# ─────────────────────────────────────────────────────────────────────────
# MODAL — entrada de valores (depositar/sacar)
# ─────────────────────────────────────────────────────────────────────────

class AmountModal(Modal):
    def __init__(self, title: str, on_submit_callback):
        super().__init__(title=title)
        self.on_submit_callback = on_submit_callback
        self.amount = TextInput(label="Quantidade de moedas", placeholder="100")
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount.value)
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Digite um número válido maior que zero.", ephemeral=True)
            return
        await self.on_submit_callback(interaction, amount)


# ─────────────────────────────────────────────────────────────────────────
# VIEW PRINCIPAL — console com select de navegação
# ─────────────────────────────────────────────────────────────────────────

SCREEN_OPTIONS = [
    discord.SelectOption(label="Início",      value="home",      emoji="🏠"),
    discord.SelectOption(label="Pet",         value="pet",       emoji="🐾"),
    discord.SelectOption(label="Mochila",     value="inventory", emoji="🎒"),
    discord.SelectOption(label="Equipamento", value="equip",     emoji="⚔️"),
    discord.SelectOption(label="Loja",        value="shop",      emoji="🏪"),
    discord.SelectOption(label="Banco",       value="bank",      emoji="🏦"),
    discord.SelectOption(label="Guilda",      value="guild",     emoji="🏰"),
    discord.SelectOption(label="Status",      value="status",    emoji="⚡"),
    discord.SelectOption(label="Instruções",  value="help",      emoji="📖"),
]


def render_screen(bot, server_id, user_id, screen, inv_page=1):
    """Retorna (embed, file_or_None) para a tela atual."""
    if screen == "pet":
        return screen_pet(server_id, user_id)
    elif screen == "inventory":
        return screen_inventory(user_id, inv_page), None
    elif screen == "equip":
        return screen_equip(user_id), None
    elif screen == "shop":
        embed, _ = screen_shop()
        return embed, None
    elif screen == "bank":
        return screen_bank(server_id, user_id), None
    elif screen == "guild":
        return screen_guild(bot, server_id), None
    elif screen == "status":
        return screen_status(server_id, user_id), None
    elif screen == "help":
        return screen_help(), None
    else:
        return screen_home(server_id, user_id), None


class GameBoyConsole(View):
    def __init__(self, bot: commands.Bot, server_id: str, user_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.server_id = server_id
        self.user_id = user_id
        self.screen = "home"
        self.inv_page = 1
        self._build()

    # ── construção dinâmica dos componentes ────────────────────────────

    def _build(self):
        self.clear_items()

        nav = Select(placeholder="📺 Selecione uma tela...", options=SCREEN_OPTIONS, row=0)
        nav.callback = self._on_nav
        self.add_item(nav)

        if self.screen == "pet":
            self.add_item(self._btn("🍖 Alimentar", discord.ButtonStyle.primary, self._feed, row=1))
            self.add_item(self._btn("🎾 Brincar", discord.ButtonStyle.success, self._play, row=1))

        elif self.screen == "inventory":
            self.add_item(self._btn("◀", discord.ButtonStyle.secondary, self._inv_prev, row=1))
            self.add_item(self._btn("▶", discord.ButtonStyle.secondary, self._inv_next, row=1))

        elif self.screen == "equip":
            equipable = self._equipable_items()
            if equipable:
                options = []
                for it in equipable[:25]:
                    r = RARITY_EMOJI.get(it["rarity"], "⚪")
                    options.append(discord.SelectOption(
                        label=f"{it['name'][:20]} ({it['slot']})",
                        value=str(it["id"]),
                        emoji=r,
                    ))
                eq_select = Select(placeholder="Escolha um item p/ equipar", options=options, row=1)
                eq_select.callback = self._on_equip_select
                self.add_item(eq_select)

            for slot in ("head", "body", "accessory", "weapon"):
                self.add_item(self._btn(f"Tirar {SLOT_EMOJI.get(slot,'')}",
                                         discord.ButtonStyle.secondary,
                                         self._make_unequip(slot), row=2))

        elif self.screen == "shop":
            _, items = screen_shop()
            if items:
                options = []
                for it in items[:25]:
                    r = RARITY_EMOJI.get(it["rarity"], "⚪")
                    options.append(discord.SelectOption(
                        label=f"{it['name'][:20]} — {it['base_price']}c",
                        value=str(it["id"]),
                        emoji=r,
                    ))
                shop_select = Select(placeholder="Escolha um item p/ comprar", options=options, row=1)
                shop_select.callback = self._on_shop_select
                self.add_item(shop_select)

        elif self.screen == "bank":
            self.add_item(self._btn("💰 Depositar", discord.ButtonStyle.success, self._deposit, row=1))
            self.add_item(self._btn("💸 Sacar", discord.ButtonStyle.danger, self._withdraw, row=1))

    def _btn(self, label, style, callback, row=0):
        b = Button(label=label, style=style, row=row)
        b.callback = callback
        return b

    def _make_unequip(self, slot):
        async def cb(interaction: discord.Interaction):
            if not await self._check_user(interaction):
                return
            db.unequip_item(self.user_id, slot)
            await self._refresh(interaction)
        return cb

    def _equipable_items(self):
        items = db.get_user_items(self.user_id, 1, 50)
        return [it for it in items if it["slot"]]

    # ── guarda: só o autor original interage ────────────────────────

    async def _check_user(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message(
                "🐾 Esse console é de outro treinador! Use `!floq` para abrir o seu.",
                ephemeral=True
            )
            return False
        return True

    # ── navegação ────────────────────────────────────────────────────

    async def _on_nav(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        self.screen = interaction.data["values"][0]
        self.inv_page = 1
        await self._refresh(interaction)

    async def _refresh(self, interaction: discord.Interaction):
        self._build()
        embed, file = render_screen(self.bot, self.server_id, self.user_id, self.screen, self.inv_page)
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)

    # ── ações: pet ───────────────────────────────────────────────────

    async def _feed(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        balance = db.get_balance(self.user_id)
        if balance < FEED_COST:
            await interaction.response.send_message(f"❌ Precisa de {FEED_COST} moedas pra alimentar.", ephemeral=True)
            return
        boost = random.randint(FEED_HAPPINESS_MIN, FEED_HAPPINESS_MAX)
        db.remove_balance(self.user_id, FEED_COST)
        db.add_happiness(self.server_id, boost)
        db.set_last_happiness_update(self.server_id, int(time.time()))
        db.update_mood(self.server_id)
        await self._refresh(interaction)

    async def _play(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        db.add_happiness(self.server_id, PLAY_HAPPINESS_BOOST)
        db.set_last_happiness_update(self.server_id, int(time.time()))
        db.update_mood(self.server_id)
        await self._refresh(interaction)

    # ── ações: inventário ───────────────────────────────────────────

    async def _inv_prev(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        self.inv_page = max(1, self.inv_page - 1)
        await self._refresh(interaction)

    async def _inv_next(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        self.inv_page += 1
        await self._refresh(interaction)

    # ── ações: equipar ──────────────────────────────────────────────

    async def _on_equip_select(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        item_id = int(interaction.data["values"][0])
        db.equip_item(self.user_id, item_id)
        await self._refresh(interaction)

    # ── ações: loja ──────────────────────────────────────────────────

    async def _on_shop_select(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return
        item_id = int(interaction.data["values"][0])
        item = db.get_new_item(item_id)
        if item is None:
            await interaction.response.send_message("❌ Item não encontrado.", ephemeral=True)
            return

        price = item["base_price"]
        balance = db.get_balance(self.user_id)
        if balance < price:
            await interaction.response.send_message(
                f"❌ Você tem {balance} moedas, mas {item['name']} custa {price}.",
                ephemeral=True
            )
            return

        db.remove_balance(self.user_id, price)
        db.add_user_item(self.user_id, item["id"])
        await interaction.response.send_message(
            f"✅ Comprou **{item['name']}** por {price} moedas! Confira na Mochila.",
            ephemeral=True
        )

    # ── ações: banco ─────────────────────────────────────────────────

    async def _deposit(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return

        async def do_deposit(modal_interaction: discord.Interaction, amount: int):
            balance = db.get_balance(self.user_id)
            if balance < amount:
                await modal_interaction.response.send_message(
                    f"❌ Você só tem {balance} moedas.", ephemeral=True
                )
                return
            db.remove_balance(self.user_id, amount)
            db.add_to_server_bank(self.server_id, amount)
            embed, _ = render_screen(self.bot, self.server_id, self.user_id, self.screen, self.inv_page)
            await modal_interaction.response.edit_message(embed=embed, view=self)

        await interaction.response.send_modal(AmountModal("Depositar moedas", do_deposit))

    async def _withdraw(self, interaction: discord.Interaction):
        if not await self._check_user(interaction):
            return

        async def do_withdraw(modal_interaction: discord.Interaction, amount: int):
            bank_balance = db.get_server_bank(self.server_id)
            if bank_balance < amount:
                await modal_interaction.response.send_message(
                    f"❌ O cofre só tem {bank_balance} moedas.", ephemeral=True
                )
                return
            db.remove_from_server_bank(self.server_id, amount)
            db.update_balance(self.user_id, amount)
            embed, _ = render_screen(self.bot, self.server_id, self.user_id, self.screen, self.inv_page)
            await modal_interaction.response.edit_message(embed=embed, view=self)

        await interaction.response.send_modal(AmountModal("Sacar moedas", do_withdraw))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


# ─────────────────────────────────────────────────────────────────────────
# COG
# ─────────────────────────────────────────────────────────────────────────

class GameBoy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="floq", aliases=["console", "menu"])
    async def floq(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            await ctx.send("🐾 O console só funciona dentro de um servidor!")
            return

        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        db.ensure_server(server_id)
        db.ensure_user(user_id)

        view = GameBoyConsole(self.bot, server_id, user_id)
        embed = screen_home(server_id, user_id)
        await ctx.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GameBoy(bot))
