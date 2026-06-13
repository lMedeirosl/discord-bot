# cogs/voice_fun.py
"""
🐕 Floq entra na call, dá uns latidos e sai
---------------------------------------------
Comando !latir (aliases: !bark, !floqlatir):
  1. Floq entra no canal de voz de quem chamou
  2. Late algumas vezes (som gerado proceduralmente, sem precisar de arquivo)
  3. Sai da call sozinho

Requer PyNacl instalado (pynacl) e libopus disponível no sistema
(a maioria dos hosts Linux já tem libopus0 instalado).
"""

import io
import math
import random
import asyncio
import discord
from discord.ext import commands

SAMPLE_RATE = 48000  # discord.py espera PCM 48kHz estéreo 16-bit


def _tone_samples(duration: float, f_start: float, f_end: float,
                   amp: float = 0.6, noise: float = 0.25) -> list[int]:
    """Gera amostras de um 'latido': tom descendente + ruído (textura de rosnado)."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        progress = i / max(n - 1, 1)
        freq = f_start + (f_end - f_start) * progress
        envelope = math.sin(math.pi * progress)  # ataque e decaimento suaves
        wave = math.sin(2 * math.pi * freq * t)
        val = amp * envelope * (wave + noise * random.uniform(-1, 1))
        val = max(-1.0, min(1.0, val))
        samples.append(int(val * 32767))
    return samples


def _silence_samples(duration: float) -> list[int]:
    return [0] * int(SAMPLE_RATE * duration)


def generate_bark_pcm(num_barks: int = 3) -> bytes:
    """Monta PCM raw estéreo 16-bit 48kHz com 1-3 'au au au!' do Floq."""
    samples: list[int] = []
    for i in range(num_barks):
        f_start = random.randint(550, 750)
        f_end   = random.randint(150, 280)
        dur     = random.uniform(0.12, 0.22)
        samples.extend(_tone_samples(dur, f_start, f_end))
        if i < num_barks - 1:
            samples.extend(_silence_samples(random.uniform(0.08, 0.16)))

    # cauda de silêncio para não cortar o som abruptamente
    samples.extend(_silence_samples(0.2))

    # empacota como estéreo (duplica canal) 16-bit little-endian
    buf = io.BytesIO()
    for s in samples:
        packed = s.to_bytes(2, byteorder="little", signed=True)
        buf.write(packed)  # canal esquerdo
        buf.write(packed)  # canal direito
    buf.seek(0)
    return buf.read()


class VoiceFun(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="latir", aliases=["bark", "floqlatir"])
    @commands.cooldown(1, 15, commands.BucketType.guild)
    async def bark(self, ctx: commands.Context) -> None:
        if not ctx.guild:
            await ctx.send("🐾 Isso só funciona dentro de um servidor!")
            return

        voice_state = ctx.author.voice
        if voice_state is None or voice_state.channel is None:
            await ctx.send(f"🐾 {ctx.author.mention}, entra numa call primeiro! Floq não acha você. 👀")
            return

        channel = voice_state.channel

        try:
            vc = await channel.connect()
        except discord.ClientException:
            # já conectado em outro canal desse servidor
            vc = ctx.guild.voice_client
            if vc and vc.channel != channel:
                await vc.move_to(channel)
        except Exception as e:
            await ctx.send(f"❌ Floq tentou entrar na call mas escorregou: `{e}`")
            return

        await ctx.send(f"🐕 *Floq entra correndo na call* **{channel.name}**! Au au au! 🐾")

        try:
            num_barks = random.randint(2, 4)
            pcm_bytes = generate_bark_pcm(num_barks)
            source = discord.PCMAudio(io.BytesIO(pcm_bytes))

            done = asyncio.Event()

            def _after(error):
                self.bot.loop.call_soon_threadsafe(done.set)

            vc.play(source, after=_after)
            await done.wait()

            # pequena pausa antes de sair, pra não parecer um "hit and run"
            await asyncio.sleep(1.0)
        finally:
            await vc.disconnect()
            await ctx.send("🐕 *Floq sai correndo da call, missão cumprida!* 🐾💨")

    @bark.error
    async def bark_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"🐾 Floq ainda está descansando a garganta! "
                f"Tenta de novo em **{error.retry_after:.0f}s**."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceFun(bot))
