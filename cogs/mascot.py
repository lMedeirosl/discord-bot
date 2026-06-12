# cogs/mascot.py
import time
import random
import io
import discord
from discord.ext import commands, tasks
from discord.ui import View
from PIL import Image, ImageDraw, ImageFont
import db
import item_manager

XP_PER_COMMAND = 10
FEED_COST = 50
FEED_HAPPINESS_MIN = 5
FEED_HAPPINESS_MAX = 10
PLAY_HAPPINESS_BOOST = 5
DECAY_MINUTES = 10
DECAY_AMOUNT = 2

ASSETS_PATH = "assets/"
CANVAS_SIZE = (400, 300)
MASCOT_CENTER = (200, 140)

# cores por raridade — usadas para colorir acessórios equipados
RARITY_COLORS = {
    "common":    (200, 200, 200),
    "uncommon":  (110, 230, 120),
    "rare":      (90, 160, 255),
    "epic":      (190, 110, 255),
    "legendary": (255, 210, 60),
}

# fundo / clima por humor
MOOD_BACKGROUND = {
    "happy":   (40, 90, 55),
    "neutral": (30, 60, 40),
    "sad":     (35, 45, 60),
    "chaotic": (70, 35, 35),
}

MOOD_LABELS = {
    "happy":   "😊 Feliz",
    "neutral": "😐 Neutro",
    "sad":     "😢 Triste",
    "chaotic": "🌀 Caótico",
}


def draw_bar(draw, x, y, width, height, value, max_val, color):
    draw.rectangle([x, y, x+width, y+height], fill=(60,64,72), outline=(30,34,42))
    fill_w = int(width * (value / max_val))
    if fill_w > 0:
        draw.rectangle([x, y, x+fill_w, y+height], fill=color)


def generate_mascot_image(server_id, user_id):
    mascot = db.get_mascot(server_id)
    level = mascot["level"]
    happiness = mascot["happiness"]
    name = mascot["mascot_name"]
    mood = db.get_mood(server_id)

    equipped = db.get_equipped_items(user_id)
    items_by_slot = {}
    for eq in equipped:
        items_by_slot[eq["slot"]] = eq  # sqlite3.Row: tem name, rarity, slot...

    bg_color = MOOD_BACKGROUND.get(mood, MOOD_BACKGROUND["neutral"])

    # Canvas estilo Game Boy
    canvas = Image.new("RGB", CANVAS_SIZE, bg_color)
    draw = ImageDraw.Draw(canvas)

    # borda
    draw.rectangle([5, 5, CANVAS_SIZE[0]-6, CANVAS_SIZE[1]-6], outline=(10, 25, 10), width=3)

    px = 5
    cx, cy = MASCOT_CENTER  # (200, 140)

    def pixel(x, y, cor):
        x1 = cx + x * px
        y1 = cy + y * px
        draw.rectangle([x1, y1, x1+px-1, y1+px-1], fill=cor)

    white = (255,255,255)
    off_white = (230,230,230)
    black = (0,0,0)
    pink = (255,180,180)
    brown = (100,60,30)
    blue_tear = (120,180,255)
    red = (255,80,80)

    # ========== CORPO (perfil, oval horizontal) ==========
    corpo = [
        (-4, 1), (-3, 0), (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (3, 0), (4, 1),
        (-5, 2), (-4, 1), (-3, 1), (-2, 1), (-1, 1), (0, 1), (1, 1), (2, 1), (3, 1), (4, 2), (5, 2),
        (-5, 3), (-4, 2), (-3, 2), (-2, 2), (-1, 2), (0, 2), (1, 2), (2, 2), (3, 2), (4, 3), (5, 3),
        (-4, 3), (-3, 3), (-2, 3), (-1, 3), (0, 3), (1, 3), (2, 3), (3, 3), (4, 3),
        (-3, 4), (-2, 4), (-1, 4), (0, 4), (1, 4), (2, 4), (3, 4),
    ]
    for x,y in corpo:
        pixel(x, y, white)

    # ========== CABEÇA (focinho alongado à esquerda) ==========
    cabeca = [
        (-6, -3), (-5, -4), (-4, -4), (-3, -4), (-2, -4), (-1, -4), (0, -4), (1, -4),
        (-7, -2), (-6, -3), (-5, -3), (-4, -3), (-3, -3), (-2, -3), (-1, -3), (0, -3), (1, -3), (2, -2),
        (-7, -1), (-6, -2), (-5, -2), (-4, -2), (-3, -2), (-2, -2), (-1, -2), (0, -2), (1, -1),
        (-6, 0), (-5, -1), (-4, -1), (-3, -1), (-2, -1), (-1, -1), (0, 0),
        (-5, 1), (-4, 0), (-3, 0), (-2, 0), (-1, 0),
    ]
    for x,y in cabeca:
        pixel(x, y, white)

    # ========== ORELHA ==========
    if mood == "sad":
        orelha = [(-5, -6), (-4, -6), (-4, -5), (-3, -4), (-3, -3), (-2, -3), (-2, -2)]
    else:
        orelha = [(-5, -6), (-4, -6), (-3, -5), (-2, -4), (-1, -3)]
    for x,y in orelha:
        pixel(x, y, off_white)

    # ========== OLHO (varia com o humor) ==========
    if mood == "happy":
        pixel(-4, -2, black)
        pixel(-3, -2, black)
        pixel(-3, -3, black)
        pixel(-4, -3, white)  # brilho extra de felicidade
    elif mood == "sad":
        pixel(-4, -1, black)
        pixel(-3, -1, black)
        pixel(-4, -2, off_white)  # pálpebra caída
        pixel(-3, 0, blue_tear)   # lágrima
    elif mood == "chaotic":
        pixel(-4, -2, black)
        pixel(-3, -3, black)
        pixel(-4, -3, black)
        pixel(-3, -2, white)
    else:  # neutral
        pixel(-4, -2, black)
        pixel(-3, -2, black)
        pixel(-3, -3, black)

    # ========== NARIZ ==========
    pixel(-7, -1, black)
    pixel(-6, -1, black)
    pixel(-6, 0, black)

    # ========== BOCA (varia com o humor) ==========
    if mood == "happy":
        pixel(-5, 1, brown)
        pixel(-4, 1, brown)
        pixel(-3, 2, brown)
        pixel(-4, 2, pink)   # língua
        pixel(-5, 2, pink)
    elif mood == "sad":
        pixel(-5, 1, brown)
        pixel(-4, 2, brown)
        pixel(-3, 2, brown)
    elif mood == "chaotic":
        pixel(-5, 1, brown)
        pixel(-4, 1, brown)
        pixel(-3, 1, brown)
        pixel(-4, 2, pink)
        pixel(-3, 2, pink)
        pixel(-5, 2, brown)
    else:  # neutral
        pixel(-5, 1, brown)
        pixel(-4, 1, brown)
        pixel(-3, 2, brown)

    # ========== BOCHECHA ROSADA ==========
    pixel(-3, 0, pink)
    pixel(-2, 0, pink)

    # ========== PATAS ==========
    pata_frente = [(-2, 4), (-1, 4), (0, 4)]
    pata_tras = [(3, 3), (4, 3), (5, 3)]
    for x,y in pata_frente:
        pixel(x, y, off_white)
    for x,y in pata_tras:
        pixel(x, y, off_white)

    # ========== RABO (varia com o humor) ==========
    if mood == "happy":
        rabo = [(5, 0), (6, -1), (7, -2), (6, -3), (5, -4)]
    elif mood == "sad":
        rabo = [(5, 2), (6, 3), (6, 4)]
    elif mood == "chaotic":
        rabo = [(5, 0), (6, -1), (6, -2), (5, -3), (7, 0), (7, -3)]
    else:
        rabo = [(5, 0), (6, -1), (6, -2), (5, -3)]
    for x,y in rabo:
        pixel(x, y, white)

    # ========== EFEITOS EXTRAS DE HUMOR ==========
    if mood == "happy":
        for x, y in [(-1, -7), (1, -8), (3, -7)]:
            pixel(x, y, (255, 120, 160))  # corações
    elif mood == "sad":
        for x, y in [(-2, -8), (-1, -8), (0, -8), (-1, -7)]:
            pixel(x, y, (100, 110, 130))  # nuvem
        pixel(-1, -6, blue_tear)
    elif mood == "chaotic":
        for x, y in [(-8, 3), (-9, 2), (8, 2), (9, 1), (-8, -4), (8, -4)]:
            pixel(x, y, white)  # linhas de zoomies
        pixel(2, -5, red)
        pixel(-6, -5, red)

    # ========== EQUIPAMENTOS (procedural, colorido por raridade) ==========
    for slot, item in items_by_slot.items():
        color = RARITY_COLORS.get(item["rarity"], RARITY_COLORS["common"])

        if slot == "head":
            for x, y in [(-6, -5), (-5, -5), (-4, -5), (-3, -5), (-2, -5), (-1, -5), (0, -5),
                         (-5, -6), (-4, -6), (-3, -6), (-2, -6)]:
                pixel(x, y, color)

        elif slot == "accessory":
            for x, y in [(-2, 0), (-1, 0), (0, 0), (1, 0), (-2, 1)]:
                pixel(x, y, color)
            pixel(-1, 1, white)  # pingente

        elif slot == "body":
            for x, y in [(-1, 1), (0, 1), (1, 1), (2, 1), (-1, 2), (0, 2), (1, 2), (2, 2)]:
                pixel(x, y, color)
            for x, y in [(-1, 1), (2, 2)]:
                pixel(x, y, off_white)  # listra de destaque

        elif slot == "weapon":
            for x, y in [(-9, 0), (-8, 0), (-8, 1)]:
                pixel(x, y, color)
            pixel(-9, 1, off_white)

    # UI texto e barra
    draw.text((10, 10), f"{name} Lv.{level}", fill=(255,255,255))
    draw.text((10, 30), f"🐾 Maltês Pixel  •  {MOOD_LABELS.get(mood, mood)}", fill=(200,255,200))
    draw_bar(draw, 10, 50, 150, 12, happiness, 100, (120,255,120))
    draw.text((165, 48), f"{happiness}%", fill=(255,255,255))

    if items_by_slot:
        eq_names = ", ".join(item["name"] for item in items_by_slot.values())
        draw.text((10, 270), f"Equipado: {eq_names}", fill=(220,220,220))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    return buf

class MascotView(View):
    def __init__(self, ctx, server_id, user_id):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.server_id = server_id
        self.user_id = user_id

    async def update(self, interaction):
        buf = generate_mascot_image(self.server_id, self.user_id)
        file = discord.File(buf, filename="mascot.png")
        mood = db.get_mood(self.server_id)
        embed = discord.Embed(
            title="🐾 Floq",
            description=f"Mascote interativo — {MOOD_LABELS.get(mood, mood)}",
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://mascot.png")
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    @discord.ui.button(label="🍖 Alimentar", style=discord.ButtonStyle.primary)
    async def feed(self, interaction, button):
        balance = db.get_balance(self.user_id)
        if balance < FEED_COST:
            await interaction.response.send_message(f"Precisa de {FEED_COST} moedas.", ephemeral=True)
            return
        boost = random.randint(FEED_HAPPINESS_MIN, FEED_HAPPINESS_MAX)
        db.remove_balance(self.user_id, FEED_COST)
        db.add_happiness(self.server_id, boost)
        db.set_last_happiness_update(self.server_id, int(time.time()))
        await self.update(interaction)

    @discord.ui.button(label="🎾 Brincar", style=discord.ButtonStyle.success)
    async def play(self, interaction, button):
        db.add_happiness(self.server_id, PLAY_HAPPINESS_BOOST)
        db.set_last_happiness_update(self.server_id, int(time.time()))
        await self.update(interaction)

    @discord.ui.button(label="🎒 Inv", style=discord.ButtonStyle.secondary)
    async def inv(self, interaction, button):
        items = db.get_user_items(self.user_id, 1, 5)
        if not items:
            text = "Inventário vazio."
        else:
            text = "\n".join([f"{i['name']} x{i['quantity']}" for i in items[:5]])
        await interaction.response.send_message(f"Inventário:\n{text}", ephemeral=True)


class Mascot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.happiness_decay_loop.start()

    def cog_unload(self):
        self.happiness_decay_loop.cancel()

    @tasks.loop(minutes=DECAY_MINUTES)
    async def happiness_decay_loop(self):
        with db.get_connection() as conn:
            servers = conn.execute("SELECT server_id FROM servers").fetchall()
        for row in servers:
            db.add_happiness(row["server_id"], -DECAY_AMOUNT)

    @commands.command(name="pet")
    async def pet(self, ctx):
        if not ctx.guild:
            await ctx.send("Apenas em servidores.")
            return
        server_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        db.ensure_server(server_id)
        db.ensure_user(user_id)
        db.add_xp(server_id, XP_PER_COMMAND)
        db.update_mood(server_id)
        mood = db.get_mood(server_id)
        buf = generate_mascot_image(server_id, user_id)
        file = discord.File(buf, filename="mascot.png")
        embed = discord.Embed(
            title="🐾 Floq",
            description=f"Mascote interativo — {MOOD_LABELS.get(mood, mood)}",
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://mascot.png")
        view = MascotView(ctx, server_id, user_id)
        await ctx.send(embed=embed, file=file, view=view)


async def setup(bot):
    await bot.add_cog(Mascot(bot))
