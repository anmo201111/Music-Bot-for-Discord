import re
import discord
from discord.ext import commands
import asyncio
from discord import FFmpegPCMAudio
import yt_dlp as youtube_dl  
from discord.ext.commands import CommandNotFound

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Per-guild queues, current song, and loop flags
music_queues = {}
current_song = {}
looping = {}

ytdl_opts = {
     'format': 'bestaudio[acodec=opus]/bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'default_search': 'auto',
    'source_address': None,
}


ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -af "aresample=48000,volume=1.0"',
}



def search_youtube(query: str) -> str | None:
    """Always extract a direct audio URL from yt-dlp."""
    with youtube_dl.YoutubeDL(ytdl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            return info.get('url')
        except Exception as e:
            print(f"[yt-dlp error] {e}")
    return None

async def play_next(ctx: commands.Context):
    """Play the next song in the queue, handling looping."""
    gid = ctx.guild.id
    queue = music_queues.get(gid, [])
    # If queue empty but looping enabled, re-add current song
    if not queue:
        if looping.get(gid) and current_song.get(gid):
            queue.append(current_song[gid])
        else:
            return
    # Pop next song
    song = queue.pop(0)
    music_queues[gid] = queue
    current_song[gid] = song
    source = FFmpegPCMAudio(song['url'], **ffmpeg_opts)
    vc = ctx.voice_client
    vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
    await ctx.send(f"▶ Now playing: **{song['title']}**")

@bot.command()
async def join(ctx):
    if not ctx.author.voice:
        return await ctx.send("❌ You need to join a voice channel first.")
    await ctx.author.voice.channel.connect()
    await ctx.send(f"✅ Joined **{ctx.author.voice.channel.name}**!")

@bot.command()
async def leave(ctx):
    if vc := ctx.voice_client:
        await vc.disconnect()
        await ctx.send("👋 Left the voice channel.")
    else:
        await ctx.send("❌ I'm not in a voice channel.")

@bot.command()
async def play(ctx: commands.Context, *, query: str):
    if not ctx.voice_client:
        await join(ctx)

    audio_url = search_youtube(query)
    if not audio_url:
        return await ctx.send("⚠️ Couldn't find any results.")

    gid = ctx.guild.id
    queue = music_queues.setdefault(gid, [])
    queue.append({'url': audio_url, 'title': query, 'added_by' : ctx.author.name})
    music_queues[gid] = queue
    # If nothing is playing, start playback
    vc = ctx.voice_client
    if not vc.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"➕ Added to queue: **{query}**")

@bot.command()
async def pause(ctx: commands.Context):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await ctx.send("⏸ Paused.")
    else:
        await ctx.send("❌ Nothing is playing.")

@bot.command()
async def resume(ctx: commands.Context):
    vc = ctx.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await ctx.send("▶ Resumed.")
    else:
        await ctx.send("❌ Nothing is paused.")

@bot.command()
async def skip(ctx: commands.Context):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send("⏭ Skipped.")
    else:
        await ctx.send("❌ Nothing is playing.")

@bot.command()
async def stop(ctx: commands.Context):
    vc = ctx.voice_client
    if vc:
        music_queues.pop(ctx.guild.id, None)
        current_song.pop(ctx.guild.id, None)
        await vc.disconnect()
        await ctx.send("⏹ Stopped and left.")
    else:
        await ctx.send("❌ I'm not in a voice channel.")

@bot.command()
async def queue(ctx: commands.Context):
    queue = music_queues.get(ctx.guild.id, [])
    if not queue:
        return await ctx.send("📭 Queue is empty.")
    lines = [f"{i+1}. {item['title']} (added by {item['added_by']})" for i, item in enumerate(queue)]
    await ctx.send("📜 **Current Queue:**\n" + "\n".join(lines))

@bot.command()
async def clearqueue(ctx: commands.Context):
    music_queues.pop(ctx.guild.id, None)
    await ctx.send("🗑 Queue cleared.")

@bot.command()
async def loop(ctx: commands.Context):
    gid = ctx.guild.id
    if not current_song.get(gid):
        return await ctx.send("❌ Nothing is playing to loop.")
    looping[gid] = not looping.get(gid, False)
    status = "enabled" if looping[gid] else "disabled"
    await ctx.send(f"🔁 Looping is now **{status}**.")

@bot.command()
async def clearloop(ctx: commands.Context):
    looping.pop(ctx.guild.id, None)
    await ctx.send("🔁 Loop disabled.")



bot.run("") # Replace with your bot token
