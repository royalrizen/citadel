import discord
import json
from discord.ext import commands
from discord import app_commands as slash
from utils.staff import is_event_team
import config
import yaml

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.list_file = 'list.json'
        self.register_btn = RegisterButton(self.bot)
        with open('settings.yaml', 'r') as f:
            self.settings = yaml.safe_load(f)

    async def cog_load(self):
        self.bot.add_view(self.register_btn)

    async def cog_unload(self):
        await self.register_btn.wait()

    @slash.command(name="group", description="Divide participants into groups.")
    @slash.check(is_event_team)
    @slash.describe(teams="Number of groups to divide the participants into. Default is 2.")
    async def _group(self, interaction: discord.Interaction, teams: int = None):
        try:
            with open(self.list_file, 'r') as file:
                participants = json.load(file)
            
            if not isinstance(participants, list) or not participants:
                raise ValueError("The participants list is empty.")
            
            if teams is None:
            	teams = 2
            	
            if not teams <= 2:
                await interaction.response.send_message(
                    "The number of teams must be greater than two.", ephemeral=True
                )
                return
            
            group_size = len(participants) // teams
            remainder = len(participants) % teams

            groups = []
            start = 0
            for i in range(teams):
                size = group_size + (1 if remainder > 0 else 0)
                groups.append(participants[start:start + size])
                start += size
                remainder -= 1

            formatted_groups = "\n\n".join(
                [f"**Team {i+1}:**\n" + "\n".join(group) for i, group in enumerate(groups)]
            )

            await interaction.response.send_message(
                f"Participants divided into {teams} groups:\n\n{formatted_groups}",
                ephemeral=True
            )
        except FileNotFoundError:
            await interaction.response.send_message(
                "The participants list does not exist.", ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                str(e), ephemeral=True
            )

    @slash.command(name="register-event",
                   description="Post the Event Registration embed")
    @slash.guild_only()
    @slash.check(is_event_team)
    @slash.describe(
        channel="Channel to post the Event Registration embed")
    async def _register_event(self,
                              interaction: discord.Interaction,
                              title: str,
                              description: str,
                              channel: discord.TextChannel = None):
        if channel is None:
            channel = interaction.channel
        embed = discord.Embed(description=f"## {config.EVENT}  Event Registration\n** **\n### __{title}__\n** **\n{description}\n** **", color=config.TRANSPARENT)

        await channel.send(embed=embed, view=self.register_btn)
        await interaction.response.send_message(
            "Successfully posted the Event Registration embed!")
            
    @slash.command(name="export", description="Exports the participant list as a JSON file.")
    @slash.check(is_event_team)
    async def _export(self, interaction: discord.Interaction):
        try:
            with open(self.list_file, 'r') as file:
                user_list = json.load(file)
                if not isinstance(user_list, list) or not user_list:
                    raise ValueError("The participant list is empty.")
            await interaction.response.send_message(
                file=discord.File(self.list_file, filename="list.json")
            )
        except FileNotFoundError:
            await interaction.response.send_message(
                "The participant list does not exist.",
                ephemeral=True
            )
        except ValueError as e:
            await interaction.response.send_message(
                str(e), ephemeral=True
            )

    @slash.command(name="import", description="Imports a participant list from a JSON file.")
    @slash.check(is_event_team)
    async def _import(self, interaction: discord.Interaction, file: discord.Attachment):
        if not file.filename.endswith(".json"):
            await interaction.response.send_message(
                "Please upload a valid JSON file.", ephemeral=True
            )
            return

        try:
            data = await file.read()
            new_list = json.loads(data)
            if not isinstance(new_list, list):
                raise ValueError("Invalid JSON format.")
        except Exception:
            await interaction.response.send_message(
                "Unable to parse the JSON file.", ephemeral=True
            )
            return

        confirmation_view = ConfirmOverwriteView(self.list_file, new_list, "Participants list has been imported successfully.")
        await interaction.response.send_message(
            "This will erase the current participants list. Do you wish to continue?",
            view=confirmation_view,
            ephemeral=True,
        )

    @slash.command(name="clear", description="Clears the participant list.")
    @slash.check(is_event_team)
    async def _clear(self, interaction: discord.Interaction):
        try:
            with open(self.list_file, 'r') as file:
                user_list = json.load(file)
                if not isinstance(user_list, list) or not user_list:
                    raise ValueError("The participant list is already empty.")
        except FileNotFoundError:
            await interaction.response.send_message(
                "The participant list does not exist.", ephemeral=True
            )
            return
        except ValueError as e:
            await interaction.response.send_message(
                str(e), ephemeral=True
            )
            return

        confirmation_view = ConfirmOverwriteView(self.list_file, [], "Participants list has been cleared.")
        await interaction.response.send_message(
            "This will clear the current participants list. Do you wish to continue?",
            view=confirmation_view,
            ephemeral=True,
        )


class ConfirmOverwriteView(discord.ui.View):
    def __init__(self, list_file, new_list, success_message):
        super().__init__(timeout=60)
        self.list_file = list_file
        self.new_list = new_list
        self.success_message = success_message

    @discord.ui.button(label="Yes, do it", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            with open(self.list_file, 'w') as file:
                json.dump(self.new_list, file, indent=4)
        except Exception as e:
            await interaction.response.edit_message(
                content=f"Failed to update the list. {str(e)}",
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=self.success_message,
            view=None,
        )
        await interaction.channel.sendo(f"{interaction.user.mention} has overwritten the participant list."
        )

class RegisterButton(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.list_file = 'list.json'
        with open('settings.yaml', 'r') as f:
            self.settings = yaml.safe_load(f)
        
    @discord.ui.button(label="Register", style=discord.ButtonStyle.blurple, custom_id="_register")
    async def register_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)

        try:
            with open(self.list_file, 'r') as file:
                user_list = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            user_list = []
            with open(self.list_file, 'w') as file:
                json.dump(user_list, file, indent=4)

        if user_id in user_list:
            confirmation_view = ConfirmCancellationView(user_id, self.list_file)
            await interaction.response.send_message(
                "You've already registered for the event. Do you wish to cancel it?",
                view=confirmation_view,
                ephemeral=True,
            )
        else:
            user_list.append(user_id)
            with open(self.list_file, 'w') as file:
                json.dump(user_list, file, indent=4)

            guild = interaction.guild
            participant_role = guild.get_role(self.settings['event_settings']['participant_role'])            

            await interaction.user.add_roles(participant_role)
            embed = discord.Embed(description=f"{config.EVENT} {interaction.user.mention} has registered for the {title} event.", color=config.TRANSPARENT)
            channel = self.bot.get_channel(self.settings['event_settings']['registration_log'])
            await channel.send(embed=embed)
            
            await interaction.response.send_message(
                "You have been successfully registered for the event.", ephemeral=True
            )

class ConfirmCancellationView(discord.ui.View):
    def __init__(self, user_id, list_file):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.list_file = list_file
        with open('settings.yaml', 'r') as f:
            self.settings = yaml.safe_load(f)
        
    @discord.ui.button(label="Yes, cancel my registration", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            with open(self.list_file, 'r') as file:
                user_list = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            user_list = []

        if self.user_id in user_list:
            user_list.remove(self.user_id)
            with open(self.list_file, 'w') as file:
                json.dump(user_list, file, indent=4)

            guild = interaction.guild
            participant_role = guild.get_role(self.settings['event_settings']['participant_role'])
            
            await interaction.user.remove_roles(participant_role)
            embed = discord.Embed(description=f":x: {interaction.user.mention} has cancelled registration for the {title} event.", color=0xFF0000)
            channel = self.bot.get_channel(self.settings['event_settings']['registration_log'])
            await channel.send(embed=embed)
        await interaction.response.edit_message(
            content="Your registration has been cancelled.",
            view=None,
        )

async def setup(bot):
    await bot.add_cog(Events(bot))
