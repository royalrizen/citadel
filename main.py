import discord
from discord.ext import commands
from discord.ui import View
import traceback
import asyncio 
import time
import os 
import yaml 
import config
from utils.staff import is_dev
import web
from discord.http import Route

async def custom_request(http, method, route, **kwargs):
    response = await original_request(http, method, route, **kwargs)
    if response.status == 429:
        retry_after = response.headers.get('Retry-After')
        print(f"Rate limited. Retry after: {retry_after} seconds.")
    return response

original_request = Route.request
Route.request = custom_request

with open('settings.yaml', 'r') as file:
  settings = yaml.safe_load(file)        
  prefix  = settings['prefix']
  bug_reports_channel = settings['log_channels']['bug_reports']
        
custom_status = discord.CustomActivity(name = "avengers assemble")
bot = commands.Bot(command_prefix=prefix, activity=custom_status, case_insensitive=True, intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f"\nConnected to {bot.user}\n")
    await load_extensions()

async def load_extensions():
    for filename in os.listdir('./commands'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'commands.{filename[:-3]}')
                print(f"[+] {filename[:-3]}.py — online")
            except commands.ExtensionError as e:
                print(f"[-] {filename[:-3]} — offline ({e})")

class ReportButton(View):
    def __init__(self, bot, error_message, guild_id, user_id, username, command_name, original_message):
        super().__init__(timeout=None)
        self.bot = bot
        self.error_message = error_message
        self.guild_id = guild_id
        self.user_id = user_id
        self.username = username
        self.command_name = command_name
        self.original_message = original_message  
    @discord.ui.button(label='Report Bug', style=discord.ButtonStyle.gray, custom_id="bugbtn")
    async def send_error_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        report_channel = self.bot.get_channel(bug_reports_channel) 
        if report_channel:
            report_content = (
                f"## Bug Report\n** **\n"
                f"**Guild:** {self.guild_id}\n"
                f"**Reporter ID:** {self.user_id}\n"
                f"**Username:** {self.username}\n"
                f"**Command used:** `{self.command_name}`\n"
                f"\n```python\n{self.error_message}\n```"
            )
            await report_channel.send(report_content)
            await interaction.response.send_message("Thank you for reporting the issue!", ephemeral=True)
            await self.original_message.delete()
        else:
            await interaction.response.send_message("It looks like there was an issue while submitting your report.", ephemeral=True)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        error_message = str(error)
        guild_id = ctx.guild.id
        user_id = ctx.author.id
        username = ctx.author.name
        command_name = ctx.command.name            
        view = ReportButton(bot, error_message, guild_id, user_id, username, command_name, ctx.message)
        
        error_msg = await ctx.send("Uh oh! Something went wrong. Would you like to report this bug?", view=view)
        
        view.original_message = error_msg
    else:
     	await ctx.reply(error, allowed_mentions=discord.AllowedMentions.none())
     	       
async def evaluate(ctx, code):
    try:
        result = eval(code)
        if asyncio.iscoroutine(result):
            return await result
        else:
            return result
    except Exception as e:
        return e

@bot.command(name="sync", description="Sync slash commands")
@commands.check(is_dev)
async def _sync(ctx):
    synced = await bot.tree.sync()
    await ctx.reply(embed=discord.Embed(description=f"synced **`{len(synced)}`** command(s)", color=config.SECONDARY_COLOR), allowed_mentions=discord.AllowedMentions.none())

@bot.command(name='evaluate', aliases=['eval', 'e', 'execute', 'exec'], usage="<code>", description="Evaluates your python code", pass_context=True)
@commands.check(is_dev)
async def eval_command(ctx, *, code):
    try:
        start_time = time.monotonic()
        result = await evaluate(ctx, code)
        end_time = time.monotonic()
        execution_time = (end_time - start_time) * 1000

        result_str = str(result)

        if isinstance(result, Exception):
            raise result

        if len(result_str) > 1800:
            embed = discord.Embed(color=0x27272f)
            embed.set_author(name=f"Evaluation by {ctx.author.name} - {ctx.author.id}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_footer(text=f"{execution_time:.2f} ms")

            chunks = [result_str[i:i+1800] for i in range(0, len(result_str), 1800)]
            for chunk in chunks:
                embed.description = f"```py\n{chunk}\n```"
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(description=f"```py\n{result_str}\n```", color=0x27272f)
            embed.set_author(name=f"Evaluation by {ctx.author.name} - {ctx.author.id}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
            embed.set_footer(text=f"{execution_time:.2f} ms")
            await ctx.send(embed=embed)

    except Exception as e:
        tb = traceback.format_exc()
        embed = discord.Embed(description=f"```{tb}```", color=0x27272f)
        embed.set_author(name=f"Evaluation by {ctx.author.name} - {ctx.author.id}", icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url)
        embed.set_footer(text=e)
        await ctx.message.add_reaction('❌')
        await ctx.send(embed=embed)
            
@bot.event
async def on_message(message):
    if not message.author.bot:
        await bot.process_commands(message)

web.keep_alive()
bot.remove_command('help')
bot.run(config.TOKEN)                
