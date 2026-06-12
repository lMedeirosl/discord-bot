# cogs/floq_events.py
"""
Sistema de Eventos Narrativos do Floq
--------------------------------------
• Floq manda mensagens espontâneas baseadas no humor atual do servidor
• Floq tem "memória curta": lembra do último usuário e menciona ele
• Aventuras coletivas: Floq convoca o servidor para missões, quem ajuda ganha recompensa
  - Comando !ajudar para contribuir durante uma aventura ativa
  - Comando !aventura para ver o status atual
  - Comando !historico para ver aventuras passadas
"""

import asyncio
import random
import time
import discord
from discord.ext import commands, tasks
import db

# ── timings ────────────────────────────────────────────────────────────────
FLOQ_TALK_MIN_MINUTES = 15
FLOQ_TALK_MAX_MINUTES = 40
ADVENTURE_MIN_MINUTES = 30
ADVENTURE_MAX_MINUTES = 90
ADVENTURE_DURATION_MINUTES = 10   # janela para participar
HELP_COOLDOWN_SECONDS = 30        # evita spam de !ajudar
HELP_CONTRIBUTION = 10            # pontos por !ajudar

# ── falas espontâneas por humor ────────────────────────────────────────────
FLOQ_LINES: dict[str, list[str]] = {
    "happy": [
        "🐾 *Floq dá voltas em círculos de alegria!* Hoje tá um dia lindo pra farejar o mundo!",
        "🐕 *Floq traz um graveto e deposita orgulhosamente no chat.* Alguém quer brincar?",
        "🎾 Floq achou uma bolinha! Tá feliz demais hoje. Correu tanto que a língua ficou assim... 👅",
        "🐾 *Floq observa o servidor com olhinhos brilhantes.* Vocês são a melhor matilha! 🐕✨",
        "😄 Floq está no modo 'rabo ligado no turbo'. Muito feliz hoje!",
    ],
    "neutral": [
        "🐾 *Floq boceja lentamente e te olha.* Alguém tem um petisco? Perguntando por um amigo.",
        "🐕 Floq está contemplando a vida. E também aquela ração que acabou.",
        "💭 *Floq coça a orelha pensativo.* Hoje tá quieto por aqui...",
        "🐾 Floq farejou o canal e não achou nada de especial. Mas ficou por aqui mesmo.",
        "😐 *Floq deita, suspira, levanta, dá uma volta e deita de novo.*",
    ],
    "sad": [
        "😢 *Floq olha pra janela com olhos tristes.* Ninguém me alimentou hoje...",
        "🐾 Floq está com o rabinho caído. Um pouco de atenção? Use `!pet` pra ajudar!",
        "💔 *Floq suspira fundo e vai pra casinha.* Tá triste. Alguém usa `!pet` pra dar atenção?",
        "😔 Floq está no modo dramático. Deita no chão. Coloca a patinha no rosto. Suspira.",
        "🐕 *Floq empurra a tigela vazia na sua direção.* Tá vendo isso? Tá vendo?",
    ],
    "chaotic": [
        "🌀 *Floq entra correndo, bate no móvel, sai correndo.* ZOOMIES ATIVADOS!",
        "💥 FLOQ ACORDOU DO LADO ERRADO DA CAMA. CAOS TOTAL. TODOS FUJAM. 🐕🌪️",
        "😈 *Floq olha pra você. Olha pro teclado. Olha pra você de novo.* Não faz isso, Floq— — — `@everyone`",
        "🎭 Floq decidiu que hoje é dia de drama. Ato 1: entra correndo. Ato 2: some. FIM.",
        "🐾 *Floq fareja o ar.* Cheira a CAOS hoje. Floq aprova.",
    ],
}

# ── aventuras ──────────────────────────────────────────────────────────────
ADVENTURES: list[dict] = [
    {
        "title": "🌳 A Floresta dos Esquilos",
        "description": (
            "Floq farejou algo suspeito na floresta... ESQUILOS! "
            "Ele precisa da ajuda da matilha para caçar todos antes que some. "
            "Use `!ajudar` para participar da caçada! 🐿️"
        ),
        "goal": 50,
        "reward_coins": 80,
        "reward_xp": 30,
        "success_text": "🏆 A matilha venceu os esquilos! Floq voltou vitorioso com a boca cheia de... orgulho.",
        "fail_text": "😔 Os esquilos escaparam. Floq voltou envergonhado. Mas treina e volta mais forte!",
    },
    {
        "title": "📦 O Pacote Misterioso",
        "description": (
            "Um entregador deixou um pacote suspeito na porta. "
            "Floq está farejando o pacote há 20 minutos. É presente? É ameaça? "
            "Ajudem Floq a investigar! Use `!ajudar`! 🔍"
        ),
        "goal": 40,
        "reward_coins": 60,
        "reward_xp": 25,
        "success_text": "🎁 Era um presente! Floq abriu com as patas e achou petiscos pra todo mundo!",
        "fail_text": "📦 Ninguém ajudou a tempo. Floq empurrou o pacote pra debaixo do sofá. Por precaução.",
    },
    {
        "title": "🌧️ O Grande Banho",
        "description": (
            "O dono quer dar banho no Floq. BANHO. "
            "Floq está fugindo pelo servidor em pânico. "
            "Protejam Floq do banheiro! Use `!ajudar` para criar distração! 🚿"
        ),
        "goal": 35,
        "reward_coins": 50,
        "reward_xp": 20,
        "success_text": "💨 Floq escapou do banho! Cheira a cachorro molhado de alívio.",
        "fail_text": "🛁 Floq tomou banho. Voltou limpinho, cheiroso e humilhado.",
    },
    {
        "title": "🦴 O Osso Enterrado",
        "description": (
            "Floq enterrou um osso valioso e ESQUECEU ONDE. "
            "Está escavando o servidor todo. "
            "Ajudem a encontrar antes que ele destrua tudo! Use `!ajudar`! ⛏️"
        ),
        "goal": 45,
        "reward_coins": 70,
        "reward_xp": 28,
        "success_text": "🦴 O osso foi encontrado! Floq está comemorando mastigando energicamente.",
        "fail_text": "😩 Floq desistiu. O osso está perdido para sempre. Floq está de luto.",
    },
    {
        "title": "🐱 O Gato do Vizinho",
        "description": (
            "O gato do vizinho invadiu o território. INVASÃO. "
            "Floq precisa de backup pra defender o quintal com latidos coordenados. "
            "Use `!ajudar` para latir junto! 🔔"
        ),
        "goal": 60,
        "reward_coins": 100,
        "reward_xp": 40,
        "success_text": "😤 O gato recuou! Floq defendeu o território. Herói absoluto.",
        "fail_text": "🐱 O gato ficou. Floq está fingindo que não se importa. Tá sim.",
    },
]

# ── memória: reações quando Floq menciona último usuário ──────────────────
MEMORY_LINES: list[str] = [
    "Ei, {mention}! Floq não te esqueceu não. Ainda pensando na última vez que você {action} 🐾",
    "🐕 *Floq farejas o ar e olha pra {mention}.* Lembra quando você {action}? Floq lembra.",
    "{mention} voltou? Floq estava esperando desde aquela vez que você {action} 👀🐾",
    "🐾 Psiu, {mention}... Floq sabe que você {action}. Nada passa despercebido aqui.",
]


class FloqEvents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # canal por servidor: {server_id: channel_id}
        self._channels: dict[str, int] = {}
        # cooldown de !ajudar por usuário: {user_id: last_timestamp}
        self._help_cooldowns: dict[str, int] = {}
        self.floq_talk_loop.start()
        self.adventure_loop.start()

    def cog_unload(self) -> None:
        self.floq_talk_loop.cancel()
        self.adventure_loop.cancel()

    # ── canal de eventos ───────────────────────────────────────────────────

    def _get_channel(self, server_id: str) -> discord.TextChannel | None:
        channel_id = self._channels.get(server_id)
        if channel_id:
            return self.bot.get_channel(channel_id)
        return None

    async def _send_to_server(self, server_id: str, **kwargs) -> None:
        channel = self._get_channel(server_id)
        if channel:
            try:
                await channel.send(**kwargs)
            except Exception:
                pass

    # ── falas espontâneas ──────────────────────────────────────────────────

    @tasks.loop(count=1)
    async def floq_talk_loop(self) -> None:
        while True:
            delay = random.randint(FLOQ_TALK_MIN_MINUTES * 60, FLOQ_TALK_MAX_MINUTES * 60)
            await asyncio.sleep(delay)
            for guild in self.bot.guilds:
                server_id = str(guild.id)
                if server_id not in self._channels:
                    continue
                await self._floq_speak(server_id)

    @floq_talk_loop.before_loop
    async def before_talk(self) -> None:
        await self.bot.wait_until_ready()

    async def _floq_speak(self, server_id: str) -> None:
        mood = db.get_mood(server_id)
        lines = FLOQ_LINES.get(mood, FLOQ_LINES["neutral"])
        line = random.choice(lines)

        # chance de mencionar último usuário (memória)
        if random.random() < 0.35:
            memory = db.get_floq_memory(server_id)
            if memory and memory["last_user_id"]:
                channel = self._get_channel(server_id)
                if channel:
                    guild = channel.guild
                    member = guild.get_member(int(memory["last_user_id"]))
                    if member:
                        memory_line = random.choice(MEMORY_LINES).format(
                            mention=member.mention,
                            action=memory["last_action"] or "apareceu por aqui"
                        )
                        await self._send_to_server(server_id, content=memory_line)
                        return

        await self._send_to_server(server_id, content=line)

    # ── aventuras coletivas ────────────────────────────────────────────────

    @tasks.loop(count=1)
    async def adventure_loop(self) -> None:
        while True:
            delay = random.randint(ADVENTURE_MIN_MINUTES * 60, ADVENTURE_MAX_MINUTES * 60)
            await asyncio.sleep(delay)
            for guild in self.bot.guilds:
                server_id = str(guild.id)
                if server_id not in self._channels:
                    continue
                # não inicia nova aventura se já há uma ativa
                if db.get_active_adventure(server_id):
                    continue
                await self._start_adventure(server_id)

    @adventure_loop.before_loop
    async def before_adventure(self) -> None:
        await self.bot.wait_until_ready()

    async def _start_adventure(self, server_id: str) -> None:
        template = random.choice(ADVENTURES)
        adv_id = db.create_adventure(
            server_id=server_id,
            title=template["title"],
            description=template["description"],
            goal=template["goal"],
            reward_coins=template["reward_coins"],
            reward_xp=template["reward_xp"],
        )

        embed = discord.Embed(
            title=f"🚨 Aventura começou! {template['title']}",
            description=template["description"],
            color=discord.Color.orange(),
        )
        embed.add_field(name="🎯 Meta", value=f"{template['goal']} pontos de ajuda", inline=True)
        embed.add_field(name="💰 Recompensa", value=f"{template['reward_coins']} moedas + {template['reward_xp']} XP", inline=True)
        embed.add_field(name="⏱️ Duração", value=f"{ADVENTURE_DURATION_MINUTES} minutos", inline=True)
        embed.set_footer(text=f"Use !ajudar para contribuir! ID da aventura: {adv_id}")
        await self._send_to_server(server_id, embed=embed)

        # aguarda a duração e resolve
        await asyncio.sleep(ADVENTURE_DURATION_MINUTES * 60)
        await self._resolve_adventure(server_id, adv_id, template)

    async def _resolve_adventure(self, server_id: str, adv_id: int, template: dict) -> None:
        adv = db.get_active_adventure(server_id)
        if not adv or adv["id"] != adv_id:
            return  # já foi resolvida

        success = adv["progress"] >= adv["goal"]
        db.end_adventure(adv_id, success)

        participants = db.get_adventure_participants(adv_id)

        if success:
            # distribui recompensa para todos os participantes
            for p in participants:
                db.update_balance(p["user_id"], template["reward_coins"])
            db.add_xp(server_id, template["reward_xp"])

            embed = discord.Embed(
                title=template["success_text"],
                color=discord.Color.green(),
            )
            if participants:
                heroes = ", ".join(
                    f"<@{p['user_id']}> ({p['contribution']} pts)" for p in participants[:5]
                )
                embed.add_field(name="🏅 Heróis da matilha", value=heroes, inline=False)
            embed.add_field(
                name="🎁 Recompensa distribuída",
                value=f"**{template['reward_coins']} moedas** para cada participante!",
                inline=False,
            )
        else:
            embed = discord.Embed(
                title=template["fail_text"],
                description=f"Progresso: **{adv['progress']}/{adv['goal']}** pontos. Tão perto... 😔",
                color=discord.Color.red(),
            )
            if participants:
                tried = ", ".join(f"<@{p['user_id']}>" for p in participants[:5])
                embed.add_field(name="💪 Quem tentou", value=tried, inline=False)

        embed.set_footer(text="Fique ligado para a próxima aventura do Floq!")
        await self._send_to_server(server_id, embed=embed)

    # ── comandos ───────────────────────────────────────────────────────────

    @commands.command(name="setchannel")
    @commands.has_permissions(manage_channels=True)
    async def set_channel(self, ctx: commands.Context) -> None:
        """Define o canal atual como canal de eventos do Floq."""
        server_id = str(ctx.guild.id)
        self._channels[server_id] = ctx.channel.id
        await ctx.send(
            f"✅ Canal de eventos do Floq definido para **#{ctx.channel.name}**!\n"
            "Floq vai mandar mensagens e aventuras aqui. 🐾"
        )

    @commands.command(name="ajudar")
    async def help_adventure(self, ctx: commands.Context) -> None:
        """Contribui para a aventura ativa do Floq."""
        if not ctx.guild:
            await ctx.send("Só funciona em servidores!")
            return

        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        db.ensure_user(user_id)

        adv = db.get_active_adventure(server_id)
        if not adv:
            await ctx.send("🐾 Floq não está em nenhuma aventura agora. Fique de olho!")
            return

        # cooldown por usuário
        last_help = self._help_cooldowns.get(user_id, 0)
        remaining = max(0, HELP_COOLDOWN_SECONDS - (int(time.time()) - last_help))
        if remaining > 0:
            await ctx.send(
                f"⏳ {ctx.author.mention}, espera **{remaining}s** antes de ajudar de novo!",
                delete_after=5,
            )
            return

        self._help_cooldowns[user_id] = int(time.time())
        updated = db.contribute_adventure(adv["id"], user_id, HELP_CONTRIBUTION)

        # atualiza memória
        db.update_floq_memory(server_id, user_id, "ajudou o Floq numa aventura")

        progress = updated["progress"]
        goal = updated["goal"]
        pct = min(100, int(progress / goal * 100))
        bar_filled = pct // 10
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        embed = discord.Embed(
            title=f"🐾 {adv['title']}",
            description=f"{ctx.author.mention} ajudou Floq! **+{HELP_CONTRIBUTION} pontos**",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Progresso",
            value=f"`{bar}` {progress}/{goal} ({pct}%)",
            inline=False,
        )

        if progress >= goal:
            embed.set_footer(text="🏆 Meta atingida! Aguarde o resultado...")
        else:
            embed.set_footer(text="Continue ajudando! Use !ajudar novamente em breve.")

        await ctx.send(embed=embed)

    @commands.command(name="aventura")
    async def adventure_status(self, ctx: commands.Context) -> None:
        """Mostra o status da aventura atual."""
        if not ctx.guild:
            return
        server_id = str(ctx.guild.id)
        adv = db.get_active_adventure(server_id)

        if not adv:
            await ctx.send("😴 Floq está descansando. Nenhuma aventura ativa no momento.")
            return

        progress = adv["progress"]
        goal = adv["goal"]
        pct = min(100, int(progress / goal * 100))
        bar_filled = pct // 10
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        elapsed = int(time.time()) - adv["started_at"]
        remaining_secs = max(0, ADVENTURE_DURATION_MINUTES * 60 - elapsed)
        mins, secs = divmod(remaining_secs, 60)

        embed = discord.Embed(
            title=f"⚔️ Aventura ativa: {adv['title']}",
            description=adv["description"],
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="📊 Progresso",
            value=f"`{bar}` {progress}/{goal} ({pct}%)",
            inline=False,
        )
        embed.add_field(name="⏱️ Tempo restante", value=f"{mins}m {secs}s", inline=True)
        embed.add_field(name="💰 Recompensa", value=f"{adv['reward_coins']} moedas + {adv['reward_xp']} XP", inline=True)
        embed.set_footer(text="Use !ajudar para contribuir!")
        await ctx.send(embed=embed)

    @commands.command(name="historico")
    async def adventure_history(self, ctx: commands.Context) -> None:
        """Mostra o histórico das últimas aventuras."""
        if not ctx.guild:
            return
        server_id = str(ctx.guild.id)
        adventures = db.get_last_adventures(server_id, limit=5)

        if not adventures:
            await ctx.send("📭 Nenhuma aventura concluída ainda. Use `!pet` para crescer e desbloquear eventos!")
            return

        embed = discord.Embed(
            title="📜 Histórico de Aventuras do Floq",
            color=discord.Color.dark_gold(),
        )
        for adv in adventures:
            status = "✅ Vitória" if adv["success"] else "❌ Derrota"
            embed.add_field(
                name=f"{status} — {adv['title']}",
                value=f"Progresso: {adv['progress']}/{adv['goal']} pts",
                inline=False,
            )
        await ctx.send(embed=embed)

    # ── hook: atualiza memória em comandos comuns ──────────────────────────

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            return
        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cmd = ctx.command.name if ctx.command else "fez algo"

        action_map = {
            "pet":       "visitou o Floq",
            "daily":     "pegou o daily",
            "work":      "trabalhou",
            "buy":       "comprou um item",
            "feed":      "alimentou o Floq",
            "play":      "brincou com o Floq",
            "ajudar":    "ajudou o Floq numa aventura",
        }
        action = action_map.get(cmd, f"usou o comando !{cmd}")
        db.update_floq_memory(server_id, user_id, action)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FloqEvents(bot))
