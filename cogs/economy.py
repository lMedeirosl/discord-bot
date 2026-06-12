import time
import random
import asyncio
import discord
from discord.ext import commands, tasks
from config import DAILY_REWARD, DAILY_COOLDOWN_HOURS
import db

WORK_COOLDOWN_SECONDS  = 60
WORK_MIN_REWARD        = 50
WORK_MAX_REWARD        = 150
DAILY_COOLDOWN_SECONDS = DAILY_COOLDOWN_HOURS * 3600

DEMAND_DECAY_MINUTES   = 5
EVENT_MIN_MINUTES      = 10
EVENT_MAX_MINUTES      = 20
EVENT_DURATION_MIN     = 300
EVENT_DURATION_MAX     = 600

WORK_MESSAGES = [
    "Floq farejou o bairro todo e trouxe",
    "Floq cavou o jardim e achou",
    "Floq latiu pro entregador e ganhou",
    "Floq fez um truque incrível e recebeu",
    "Floq guardou o osso e vendeu por",
]

# emojis por raridade (sistema novo) e por nome (sistema legado)
RARITY_EMOJI = {
    "common":    "⚪",
    "uncommon":  "🟢",
    "rare":      "🔵",
    "epic":      "🟣",
    "legendary": "🟡",
}

ITEM_EMOJIS = {
    "osso":           "🦴",
    "bolinha":        "🎾",
    "ração":          "🥣",
    "coleira":        "🏷️",
    "cobertor":       "🛏️",
    "coroa":          "👑",
    "capa lendária":  "🦸",
}

EVENTS = {
    "crise": {
        "multiplier": 1.20,
        "start_messages": [
            "Floq percebeu uma alta no mercado 👀📈",
            "Floq fez bagunça... os preços subiram 🐾💥",
            "O mercado do Floq entrou em crise! Tudo ficou mais caro 📈🐕",
        ],
        "end_messages": [
            "Ufa! A crise passou. Floq respirou aliviado 😮‍💨🐾",
            "O mercado acalmou. Floq voltou a abanar o rabo 🐕",
        ],
        "color": discord.Color.red(),
        "title": "📈 Crise Econômica!",
        "end_title": "📉 Crise Encerrada",
    },
    "boom": {
        "multiplier": 0.80,
        "start_messages": [
            "Floq encontrou um tesouro! Os preços caíram 🎉🐾",
            "Boom econômico! Floq está distribuindo desconto 🐕💰",
            "Floq abanou tanto o rabo que os preços despencaram 📉🎾",
        ],
        "end_messages": [
            "O boom acabou. Floq guardou os descontos na casinha 🐕",
            "Festa encerrada! Os preços voltaram ao normal 🐾",
        ],
        "color": discord.Color.green(),
        "title": "📉 Boom Econômico!",
        "end_title": "📊 Boom Encerrado",
    },
}

BUY_PRICE_RISING_MESSAGES = [
    "Hmm... esse item tá ficando caro 👀",
    "Floq notou que a demanda tá alta 📈🐾",
    "Todo mundo quer isso! O preço subiu um pouco 🐕",
]

BUY_SUCCESS_MESSAGES = [
    "Floq correu até a loja e trouxe",
    "Floq farejou o melhor preço e buscou",
    "Missão cumprida! Floq chegou com",
]

JOB_CREATE_MESSAGES = [
    "Floq anotou o serviço no caderninho 🐾📝",
    "Floq latiu anunciando o trabalho! Alguém vai aceitar? 🐕",
    "Trabalho criado! Floq ficou feliz com a oportunidade ✨",
]

JOB_ACCEPT_MESSAGES = [
    "Floq aprovou o trabalhador! Mãos à obra 🐾🔨",
    "Floq viu o aceite e abanou o rabo – serviço contratado 🐕✅",
    "Boa! O trabalho foi aceito. Floq vai fiscalizar de longe 👀🐾",
]

JOB_DONE_MESSAGES = [
    "Floq inspecionou e aprovou! Serviço concluído 🐾🏆",
    "Floq trouxe o pagamento e latiu de satisfação 💰🐕",
    "Trabalho finalizado! Floq está orgulhoso do esforço ✨",
]

def _cooldown_remaining(last_ts: int | None, cooldown_seconds: int) -> int:
    if last_ts is None:
        return 0
    try:
        last_ts = int(last_ts)
    except (TypeError, ValueError):
        return 0
    return max(0, cooldown_seconds - (int(time.time()) - last_ts))


def _format_seconds(seconds: int) -> str:
    if seconds >= 3600:
        h, r = divmod(seconds, 3600)
        return f"{h}h {r // 60}m"
    if seconds >= 60:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    return f"{seconds}s"


def _item_emoji(name: str) -> str:
    return ITEM_EMOJIS.get(name.lower(), "📦")


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._event_channel_id: int | None = None
        self._active_event: str | None = None
        self.demand_decay_loop.start()
        self.economic_event_loop.start()

    def cog_unload(self) -> None:
        self.demand_decay_loop.cancel()
        self.economic_event_loop.cancel()

    # ── background: demand decay ───────────────────────────────────────────

    @tasks.loop(minutes=DEMAND_DECAY_MINUTES)
    async def demand_decay_loop(self) -> None:
        for item in db.get_all_items():
            if item["demand"] > 0:
                db.decrease_demand(item["id"])

    @demand_decay_loop.before_loop
    async def before_decay(self) -> None:
        await self.bot.wait_until_ready()

    # ── background: economic events ────────────────────────────────────────

    @tasks.loop(count=1)
    async def economic_event_loop(self) -> None:
        while True:
            delay = random.randint(EVENT_MIN_MINUTES * 60, EVENT_MAX_MINUTES * 60)
            await asyncio.sleep(delay)

            event_key = random.choice(list(EVENTS.keys()))
            event = EVENTS[event_key]
            self._active_event = event_key

            db.apply_global_modifier(event["multiplier"])
            await self._broadcast_event(
                title=event["title"],
                description=random.choice(event["start_messages"]),
                color=event["color"],
            )

            duration = random.randint(EVENT_DURATION_MIN, EVENT_DURATION_MAX)
            await asyncio.sleep(duration)

            db.reset_prices_to_dynamic()
            self._active_event = None

            await self._broadcast_event(
                title=event["end_title"],
                description=random.choice(event["end_messages"]),
                color=discord.Color.blurple(),
            )

    @economic_event_loop.before_loop
    async def before_events(self) -> None:
        await self.bot.wait_until_ready()

    async def _broadcast_event(self, title: str, description: str, color: discord.Color) -> None:
        if self._event_channel_id is None:
            return
        channel = self.bot.get_channel(self._event_channel_id)
        if channel is None:
            return
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text="Use !shop para ver os preços atuais.")
        await channel.send(embed=embed)

    # ── commands ───────────────────────────────────────────────────────────

    @commands.command(name="saldo")
    async def balance(self, ctx: commands.Context) -> None:
        user_id = str(ctx.author.id)
        db.ensure_user(user_id)
        balance = db.get_balance(user_id)

        embed = discord.Embed(
            title="🐾 Carteira do Floq",
            description=(
                f"{ctx.author.mention}, Floq farejou sua carteira e encontrou\n"
                f"**{balance} moedas** escondidas lá dentro. 🐕"
            ),
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @commands.command(name="banco", aliases=["bank"])
    async def bank(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            await ctx.send("🐾 O banco é um cofre do servidor — use esse comando dentro de um servidor!")
            return
        server_id = str(ctx.guild.id)
        bank_balance = db.get_server_bank(server_id)

        embed = discord.Embed(
            title="🏦 Cofre do Floq",
            description=(
                f"Floq está sentado em cima do cofre do servidor, vigiando bem de perto.\n"
                f"**{bank_balance} moedas** guardadas para a matilha. 🐾"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Use !depositar <quantia> ou !sacar <quantia> (requer permissão de gerenciar servidor para sacar).")
        await ctx.send(embed=embed)

    @commands.command(name="depositar", aliases=["deposit"])
    async def deposit(self, ctx: commands.Context, amount: int) -> None:
        if not ctx.guild:
            await ctx.send("🐾 Depósitos só funcionam dentro de um servidor!")
            return
        if amount <= 0:
            await ctx.send("❌ A quantia precisa ser maior que zero.")
            return

        user_id   = str(ctx.author.id)
        server_id = str(ctx.guild.id)
        db.ensure_user(user_id)

        balance = db.get_balance(user_id)
        if balance < amount:
            embed = discord.Embed(
                title="💸 Saldo insuficiente",
                description=(
                    f"{ctx.author.mention}, você só tem **{balance} moedas**. "
                    f"Não dá pra depositar **{amount} moedas**."
                ),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        db.remove_balance(user_id, amount)
        new_bank = db.add_to_server_bank(server_id, amount)

        embed = discord.Embed(
            title="🏦 Depósito realizado!",
            description=(
                f"{ctx.author.mention} depositou **{amount} moedas** no cofre do servidor!\n"
                f"🐾 Floq guardou tudo com cuidado. Cofre agora tem **{new_bank} moedas**."
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="sacar", aliases=["withdraw"])
    @commands.has_permissions(manage_guild=True)
    async def withdraw(self, ctx: commands.Context, amount: int) -> None:
        if not ctx.guild:
            await ctx.send("🐾 Saques só funcionam dentro de um servidor!")
            return
        if amount <= 0:
            await ctx.send("❌ A quantia precisa ser maior que zero.")
            return

        user_id   = str(ctx.author.id)
        server_id = str(ctx.guild.id)
        db.ensure_user(user_id)

        bank_balance = db.get_server_bank(server_id)
        if bank_balance < amount:
            embed = discord.Embed(
                title="🏦 Cofre insuficiente",
                description=(
                    f"O cofre só tem **{bank_balance} moedas**. "
                    f"Não dá pra sacar **{amount} moedas**."
                ),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        db.remove_from_server_bank(server_id, amount)
        new_balance = db.update_balance(user_id, amount)

        embed = discord.Embed(
            title="🏦 Saque realizado!",
            description=(
                f"{ctx.author.mention} sacou **{amount} moedas** do cofre do servidor!\n"
                f"🐾 Floq entregou as moedas meio relutante. Seu saldo: **{new_balance} moedas**."
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="daily")
    async def daily(self, ctx: commands.Context) -> None:
        user_id = str(ctx.author.id)
        db.ensure_user(user_id)

        last_daily = db.get_last_daily(user_id)
        remaining = _cooldown_remaining(last_daily, DAILY_COOLDOWN_SECONDS)
        if remaining > 0:
            embed = discord.Embed(
                title="😴 Floq já descansou hoje",
                description=(
                    f"{ctx.author.mention}, Floq está cochilando no canil.\n"
                    f"Ele volta com seu daily em **{_format_seconds(remaining)}**. 🐾"
                ),
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        # streak: mantém se o último daily foi dentro de 48h, senão reseta
        now = int(time.time())
        keep_streak = (
            last_daily is not None
            and (now - int(last_daily)) <= DAILY_COOLDOWN_SECONDS * 2
        )
        streak = db.bump_daily_streak(user_id, keep_streak)

        # bônus de streak: +5% por dia consecutivo, até +100% (dia 20+)
        bonus_pct   = min(streak - 1, 20) * 5
        bonus_coins = (DAILY_REWARD * bonus_pct) // 100
        total_reward = DAILY_REWARD + bonus_coins

        new_balance = db.update_balance(user_id, total_reward)
        db.update_last_daily(user_id, now)

        bonus_line = ""
        if bonus_coins > 0:
            bonus_line = f"\n🔥 Sequência de **{streak} dias**! Bônus de streak: **+{bonus_coins} moedas** (+{bonus_pct}%)"
        elif streak == 1 and last_daily is not None:
            bonus_line = "\n💔 Sua sequência foi reiniciada. Volte amanhã pra começar a acumular bônus!"

        embed = discord.Embed(
            title="🎁 Daily do Floq!",
            description=(
                f"{ctx.author.mention}, Floq abanou o rabo e trouxe seu presente diário!\n"
                f"**+{total_reward} moedas** adicionadas. Saldo: **{new_balance} moedas** 🐕"
                f"{bonus_line}"
            ),
            color=discord.Color.green()
        )
        if streak >= 1:
            next_pct = min(streak, 20) * 5
            embed.set_footer(text=f"🔥 Streak: {streak} dia(s) • Amanhã: +{next_pct}% de bônus (máx. +100% no dia 21+)")
        await ctx.send(embed=embed)

    @commands.command(name="work")
    async def work(self, ctx: commands.Context) -> None:
        user_id = str(ctx.author.id)
        db.ensure_user(user_id)

        remaining = _cooldown_remaining(db.get_last_work(user_id), WORK_COOLDOWN_SECONDS)
        if remaining > 0:
            embed = discord.Embed(
                title="🐕 Floq ainda está no expediente",
                description=(
                    f"{ctx.author.mention}, Floq está com a língua pra fora de tanto trabalhar.\n"
                    f"Deixa ele descansar por **{_format_seconds(remaining)}**. 🐾"
                ),
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return

        reward = random.randint(WORK_MIN_REWARD, WORK_MAX_REWARD)
        new_balance = db.update_balance(user_id, reward)
        db.update_last_work(user_id, int(time.time()))

        embed = discord.Embed(
            title="💼 Floq trabalhou!",
            description=(
                f"{ctx.author.mention}, {random.choice(WORK_MESSAGES)} **{reward} moedas**!\n"
                f"Saldo atual: **{new_balance} moedas** 🐾"
            ),
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @commands.command(name="shop")
    async def shop(self, ctx: commands.Context) -> None:
        self._event_channel_id = ctx.channel.id

        items, rotated_at = db.get_shop_items()

        # fallback: se items_new estiver vazio, cai no sistema legado
        if not items:
            await self._shop_legacy(ctx)
            return

        event_note = ""
        if self._active_event:
            ev = EVENTS[self._active_event]
            event_note = f"\n⚠️ **Evento ativo:** {ev['title']} — preços afetados!"

        # tempo até próxima rotação
        next_rotation = rotated_at + db.SHOP_ROTATION_HOURS * 3600
        mins_left = max(0, (next_rotation - int(time.time())) // 60)

        embed = discord.Embed(
            title="🏪 Loja do Floq",
            description=(
                f"Floq farejou o bairro e selecionou os melhores itens de hoje!{event_note}\n"
                f"🔄 Nova seleção em **{mins_left} min**"
            ),
            color=discord.Color.teal(),
        )

        for item in items:
            rarity = item["rarity"]
            r_emoji = RARITY_EMOJI.get(rarity, "⚪")
            slot_txt = f" · `{item['slot']}`" if item["slot"] else ""
            stats = {}
            try:
                import json as _json
                stats = _json.loads(item["stats"] or "{}")
            except Exception:
                pass
            stats_txt = "  ".join(f"+{v} {k}" for k, v in stats.items()) if stats else ""

            embed.add_field(
                name=f"{r_emoji} {item['name']}",
                value=(
                    f"**{item['base_price']} moedas**{slot_txt}\n"
                    f"{stats_txt if stats_txt else '_Sem bônus_'}"
                ),
                inline=True,
            )

        embed.set_footer(
            text=(
                "Use !buy <nome> para comprar  •  "
                f"⚪common 🟢uncommon 🔵rare 🟣epic 🟡legendary  •  "
                "!shoprefresh para ver nova seleção (admin)"
            )
        )
        await ctx.send(embed=embed)

    async def _shop_legacy(self, ctx: commands.Context) -> None:
        """Fallback: loja antiga com itens hardcoded."""
        items = db.get_all_items()
        event_note = ""
        if self._active_event:
            ev = EVENTS[self._active_event]
            event_note = f"\n⚠️ **Evento ativo:** {ev['title']} — preços afetados!"
        embed = discord.Embed(
            title="🏪 Loja do Floq",
            description=f"Floq selecionou os melhores itens do bairro:{event_note}",
            color=discord.Color.teal()
        )
        for item in items:
            emoji = _item_emoji(item["name"])
            price_note = ""
            if item["current_price"] > item["base_price"]:
                price_note = " 📈"
            elif item["current_price"] < item["base_price"]:
                price_note = " 📉"
            unique_note = " ✨ **Único**" if item["is_unique"] else ""
            embed.add_field(
                name=f"{emoji} {item['name']}{unique_note}",
                value=f"**{item['current_price']} moedas**{price_note}",
                inline=True
            )
        embed.set_footer(text="Use !buy <nome> para comprar.")
        await ctx.send(embed=embed)

    @commands.command(name="shoprefresh")
    @commands.has_permissions(manage_guild=True)
    async def shop_refresh(self, ctx: commands.Context) -> None:
        """Força uma nova rotação da loja (admin)."""
        db.refresh_shop_rotation()
        await ctx.send("🔄 Nova seleção de itens gerada! Use `!shop` para ver.")

    @commands.command(name="buy")
    async def buy(self, ctx: commands.Context, *, item_name: str) -> None:
        user_id   = str(ctx.author.id)
        server_id = str(ctx.guild.id) if ctx.guild else None
        db.ensure_user(user_id)

        # tenta primeiro no catálogo novo (items_new)
        new_item = db.get_new_item_by_name(item_name)
        if new_item:
            await self._buy_new_item(ctx, user_id, server_id, dict(new_item))
            return

        # fallback: catálogo legado
        item = db.get_item_by_name(item_name)
        if item is None:
            embed = discord.Embed(
                title="🐾 Item não encontrado",
                description=(
                    f"{ctx.author.mention}, Floq farejou a loja toda e não achou **{item_name}**.\n"
                    f"Use `!shop` para ver o que está disponível."
                ),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        if item["is_unique"]:
            owner_server_id = db.get_unique_item_owner(item["id"])
            if owner_server_id is not None:
                owner_guild  = self.bot.get_guild(int(owner_server_id)) if owner_server_id else None
                owner_name   = owner_guild.name if owner_guild else f"Servidor #{owner_server_id}"
                embed = discord.Embed(
                    title="✨ Item único indisponível",
                    description=(
                        f"{ctx.author.mention}, esse item é único no mundo 🌍 e já pertence a **{owner_name}**.\n"
                        f"Outro servidor já possui isso... Floq lambe a pata de tristeza 🐾"
                    ),
                    color=discord.Color.dark_red()
                )
                await ctx.send(embed=embed)
                return

        price   = item["current_price"]
        balance = db.get_balance(user_id)

        if balance < price:
            shortage = price - balance
            embed = discord.Embed(
                title="💸 Floq ficou sem grana",
                description=(
                    f"{ctx.author.mention}, sua carteira está mais vazia que a tigela do Floq.\n"
                    f"Faltam **{shortage} moedas** para comprar **{item['name']}** por {price} moedas."
                ),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        new_balance = db.remove_balance(user_id, price)
        db.add_item_to_inventory(user_id, item["id"])
        new_price   = db.increase_demand(item["id"])

        if item["is_unique"] and server_id:
            db.register_unique_ownership(item["id"], server_id)
            db.ensure_server(server_id)
            db.add_item_to_mascot_inventory(server_id, item["id"])

        emoji      = _item_emoji(item["name"])
        price_line = ""
        if new_price > price:
            price_line = f"\n{random.choice(BUY_PRICE_RISING_MESSAGES)} Novo preço: **{new_price} moedas**."

        unique_line = ""
        if item["is_unique"]:
            unique_line = f"\n✨ **Esse item é único no mundo!** Agora ele pertence a **{ctx.guild.name if ctx.guild else 'vocês'}** 🐾"

        embed = discord.Embed(
            title=f"{emoji} Compra realizada!",
            description=(
                f"{ctx.author.mention}, {random.choice(BUY_SUCCESS_MESSAGES)} **{item['name']}** pra você!\n"
                f"Pagou **{price} moedas**. Saldo restante: **{new_balance} moedas** 🐕{price_line}{unique_line}"
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    async def _buy_new_item(self, ctx: commands.Context, user_id: str, server_id: str | None, item: dict) -> None:
        """Compra um item do catálogo novo (items_new / user_items)."""
        import json as _json
        price   = item["base_price"]
        balance = db.get_balance(user_id)

        if balance < price:
            shortage = price - balance
            r_emoji  = RARITY_EMOJI.get(item["rarity"], "⚪")
            embed = discord.Embed(
                title="💸 Floq ficou sem grana",
                description=(
                    f"{ctx.author.mention}, faltam **{shortage} moedas** para comprar "
                    f"{r_emoji} **{item['name']}** por {price} moedas."
                ),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        db.remove_balance(user_id, price)
        db.add_user_item(user_id, item["id"])

        r_emoji = RARITY_EMOJI.get(item["rarity"], "⚪")
        stats   = {}
        try:
            stats = _json.loads(item.get("stats") or "{}")
        except Exception:
            pass
        stats_txt = "  ".join(f"+{v} {k}" for k, v in stats.items()) if stats else ""
        slot_txt  = f" no slot `{item['slot']}`" if item.get("slot") else ""

        embed = discord.Embed(
            title=f"{r_emoji} Compra realizada!",
            description=(
                f"{ctx.author.mention}, {random.choice(BUY_SUCCESS_MESSAGES)} "
                f"**{item['name']}** pra você!\n"
                f"Raridade: **{item['rarity']}**{slot_txt}\n"
                f"{stats_txt if stats_txt else ''}\n"
                f"Pagou **{price} moedas**. Saldo restante: **{db.get_balance(user_id)} moedas** 🐕"
            ),
            color=discord.Color.green()
        )
        if item.get("slot"):
            embed.set_footer(text=f"Use !equip {item['id']} para equipar no Floq!")
        await ctx.send(embed=embed)

    @commands.command(name="mochila")
    async def inventory(self, ctx: commands.Context) -> None:
        user_id = str(ctx.author.id)
        db.ensure_user(user_id)

        items = db.get_user_inventory(user_id)

        if not items:
            embed = discord.Embed(
                title="🎒 Mochila do Floq",
                description=(
                    f"{ctx.author.mention}, sua mochila está vazia como um osso já roído.\n"
                    f"Visite a `!shop` e compre alguma coisa! Use `!mochila` para ver itens clássicos."
                ),
                color=discord.Color.light_grey()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🎒 Mochila do Floq",
            description=f"{ctx.author.mention}, Floq guardou tudo certinho aqui:",
            color=discord.Color.purple()
        )
        for entry in items:
            emoji = _item_emoji(entry["name"])
            embed.add_field(
                name=f"{emoji} {entry['name']}",
                value=f"Quantidade: **{entry['quantity']}**",
                inline=True
            )
        await ctx.send(embed=embed)

    @commands.command(name="globalitems")
    async def global_items(self, ctx: commands.Context) -> None:
        items = db.get_all_unique_items()

        embed = discord.Embed(
            title="✨ Itens Únicos do Mundo",
            description="Floq farejou o universo todo e encontrou esses itens raríssimos 🌍🐾",
            color=discord.Color.gold()
        )

        for item in items:
            emoji = _item_emoji(item["name"])
            if item["owner_server_id"]:
                owner_guild = self.bot.get_guild(int(item["owner_server_id"]))
                owner_name  = owner_guild.name if owner_guild else f"Servidor #{item['owner_server_id']}"
                status = f"👑 Pertence a **{owner_name}**"
            else:
                status = f"🟢 Disponível — **{item['current_price']} moedas**"

            embed.add_field(
                name=f"{emoji} {item['name']}",
                value=status,
                inline=False
            )

        if not items:
            embed.description = "Nenhum item único cadastrado ainda. Floq ficou confuso 🐕"

        embed.set_footer(text="Use !shop para comprar itens disponíveis. Cada único só pode ter um dono!")
        await ctx.send(embed=embed)

    # ── job system (Prompt 9) ──────────────────────────────────────────────

    @commands.command(name="jobcreate")
    async def job_create(self, ctx: commands.Context, payment: int) -> None:
        """Cria um trabalho oferecendo pagamento a outro usuário."""
        if payment <= 0:
            await ctx.send("❌ O pagamento precisa ser maior que zero.")
            return

        user_id = str(ctx.author.id)
        db.ensure_user(user_id)

        job_id = db.create_job(user_id, payment)
        if job_id is None:
            embed = discord.Embed(
                title="💸 Saldo insuficiente",
                description=f"{ctx.author.mention}, você não tem **{payment} moedas** para criar esse trabalho.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📋 Trabalho criado!",
            description=(
                f"{ctx.author.mention}, {random.choice(JOB_CREATE_MESSAGES)}\n"
                f"**Pagamento:** {payment} moedas\n"
                f"**ID do trabalho:** `{job_id}`"
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text="Use !jobs para ver trabalhos disponíveis e !jobaccept <id> para aceitar.")
        await ctx.send(embed=embed)

    @commands.command(name="jobs")
    async def list_jobs(self, ctx: commands.Context) -> None:
        """Lista todos os trabalhos pendentes."""
        jobs = db.get_pending_jobs()
        if not jobs:
            embed = discord.Embed(
                title="📭 Nenhum trabalho disponível",
                description="Floq olhou em todos os quadrinhos e não achou nenhum serviço aberto. Use `!jobcreate` para criar um!",
                color=discord.Color.light_gray()
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="📋 Trabalhos disponíveis",
            description="Floq organizou os serviços que estão esperando alguém 🐾",
            color=discord.Color.blurple()
        )
        for job in jobs:
            creator = await self.bot.fetch_user(int(job["creator_id"]))
            creator_name = creator.name if creator else "Desconhecido"
            embed.add_field(
                name=f"Trabalho #{job['id']}",
                value=f"Criador: {creator_name}\nPagamento: **{job['payment']} moedas**",
                inline=False
            )
        embed.set_footer(text="Use !jobaccept <id> para aceitar um trabalho.")
        await ctx.send(embed=embed)

    @commands.command(name="jobaccept")
    async def job_accept(self, ctx: commands.Context, job_id: int) -> None:
        """Aceita um trabalho para executar."""
        user_id = str(ctx.author.id)
        db.ensure_user(user_id)

        job = db.get_job(job_id)
        if not job or job["completed"] or job["accepted"]:
            await ctx.send("❌ Esse trabalho não está mais disponível.")
            return

        if job["creator_id"] == user_id:
            await ctx.send("❌ Você não pode aceitar seu próprio trabalho.")
            return

        success = db.accept_job(job_id, user_id)
        if not success:
            await ctx.send("❌ Não foi possível aceitar o trabalho. Pode ter sido aceito por outro usuário.")
            return

        embed = discord.Embed(
            title="✅ Trabalho aceito!",
            description=(
                f"{ctx.author.mention}, {random.choice(JOB_ACCEPT_MESSAGES)}\n"
                f"Trabalho #{job_id} – pagamento: **{job['payment']} moedas**.\n"
                f"Use `!jobdone {job_id}` quando concluir."
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="jobdone")
    async def job_done(self, ctx: commands.Context, job_id: int) -> None:
        """Marca um trabalho aceito como concluído e recebe o pagamento."""
        user_id = str(ctx.author.id)
        db.ensure_user(user_id)

        job = db.get_job(job_id)
        if not job or job["completed"]:
            await ctx.send("❌ Esse trabalho já foi concluído ou não existe.")
            return
        if not job["accepted"]:
            await ctx.send("❌ Esse trabalho ainda não foi aceito por ninguém.")
            return
        if job["worker_id"] != user_id:
            await ctx.send("❌ Apenas o usuário que aceitou o trabalho pode concluí-lo.")
            return

        success = db.complete_job(job_id, user_id)
        if not success:
            await ctx.send("❌ Falha ao concluir o trabalho. Tente novamente.")
            return

        embed = discord.Embed(
            title="🏆 Trabalho concluído!",
            description=(
                f"{ctx.author.mention}, {random.choice(JOB_DONE_MESSAGES)}\n"
                f"Você recebeu **{job['payment']} moedas** pelo serviço prestado!"
            ),
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Economy(bot))
