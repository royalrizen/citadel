import discord 
from discord import app_commands
from discord.ext import commands 
import os
import config
import yaml

def get_prefix(bot, message):
    with open('settings.yaml', 'r') as f:
        settings = yaml.safe_load(f)
    
    prefix = settings.get('prefix', '!')
    return prefix
  
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Get all the information about a specific command")
    @app_commands.guild_only()
    @app_commands.describe(command="Select a command")
    async def _help_command(self, interaction: discord.Interaction, command: str):
        cmd = self.bot.get_command(command)
        if cmd is None:
            await interaction.response.send_message(f"Command **{command}** not found.", ephemeral=True)
            return

        desc = cmd.description or "No description available."
        prefix = get_prefix(self.bot, interaction) if interaction.guild else '!'
        usage = f"{prefix}{cmd.qualified_name} {cmd.signature}" if cmd.signature else f"/{cmd.qualified_name}"
        aliases = ", ".join(cmd.aliases) if cmd.aliases else "No aliases."
        category = cmd.cog_name or "General"

        help_embed = discord.Embed(title=desc, color=config.SECONDARY_COLOR)
        help_embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
        help_embed.add_field(name="Aliases", value=aliases, inline=False)
        help_embed.set_footer(text=f"{category} - {command}")
        
        await interaction.response.send_message(embed=help_embed)

    @_help_command.autocomplete('command')
    async def autocomplete_command(self, interaction: discord.Interaction, current: str):
        commands_list = [cmd.qualified_name for cmd in self.bot.commands if cmd.qualified_name.startswith(current)]
        limited_commands_list = commands_list[:20]
        return [app_commands.Choice(name=cmd, value=cmd) for cmd in limited_commands_list]

async def setup(bot):
    await bot.add_cog(Help(bot))
