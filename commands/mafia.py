import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select
import random
import asyncio 

class Mafia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.games = {} 
                
    async def ensure_ghost_role(self, guild):
        """Ensure the Ghost role exists in the guild."""
        ghost_role = discord.utils.get(guild.roles, name="Ghost")
        if not ghost_role:
            ghost_role = await guild.create_role(name="Ghost", color=discord.Color.dark_gray())
        return ghost_role

    async def assign_ghost_role(self, member):
        """Assign the Ghost role to a member."""
        ghost_role = await self.ensure_ghost_role(member.guild) 
        await member.add_roles(ghost_role)

    async def remove_ghost_role(self, member):
        ghost_role = await self.ensure_ghost_role(member.guild) 
        await member.remove_roles(ghost_role)
        
    async def restore_roles(self, channel, game):
        """Remove the Ghost role from all players at the end of the game."""
        ghost_role = await self.ensure_ghost_role(channel.guild)
        for player_id in game["roles"]:
            member = discord.utils.get(channel.guild.members, id=player_id)
            await self.remove_ghost_role(member, ghost_role)
            
    @app_commands.command(name="mafia", description="Starts Mafia game.")
    @app_commands.guild_only()
    @app_commands.describe(murderers="Number of murderers in the game")
    async def _townofriz(self, interaction: discord.Interaction, murderers: app_commands.Range[int, 1, 3]):
        
        
        guild = interaction.guild        
        guild_id = interaction.guild.id
        
        ghost_role = await self.ensure_ghost_role(guild) 
        
        if guild_id in self.games:
            await interaction.response.send_message("A game is already in progress!", ephemeral=True)
            return

        game = {
            "players": [interaction.user],
            "mafia": murderers,
            "started": False,
            "game_setup_msg_id": None,
            "game_msg_id": None,
            "roles": {},
            "viewed_roles": set(),
            "phase": None,
            "votes": {},
            "night_target": None,
            "channel_id": interaction.channel.id
        }
        self.games[guild_id] = game

        embed = discord.Embed(
            title=f"Mafia",
            description="-# Mafia is a murder mystery game. Catch the murderer before he kills everyone.",
            color=0xffb900
        )
        embed.add_field(name="Players Joined", value=interaction.user.mention, inline=False)
        embed.set_footer(text=f"Hosted by {interaction.user.name}")
        setup = await interaction.channel.send(embed=embed, view=TORBTN(self, self.games[guild_id], interaction.user))
        game["game_setup_msg_id"] = setup.id

        await interaction.response.send_message("Game created! Waiting for others to join.", ephemeral=True)

class TORBTN(View):
    def __init__(self, bot, game, host):
        super().__init__(timeout=None)
        self.bot = bot
        self.game = game
        self.host = host

    @discord.ui.button(label='Join', style=discord.ButtonStyle.blurple, custom_id="joinbtn")
    async def _join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.game["players"]:
            await interaction.response.send_message("You are already in the game!", ephemeral=True)
            return

        self.game["players"].append(interaction.user)

        setup = await interaction.channel.fetch_message(self.game["game_setup_msg_id"])
        edited_setup = setup.embeds[0]
        edited_setup.set_field_at(0, name="Players Joined", value="\n".join([player.mention for player in self.game["players"]]), inline=False)
        await setup.edit(embed=edited_setup)

        await interaction.response.send_message(f"{interaction.user.mention} joined the game!", ephemeral=True)

    @discord.ui.button(label='Start', style=discord.ButtonStyle.red, custom_id="startbtn")
    async def _start(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.host:
            await interaction.response.send_message("Only the host can start the game!", ephemeral=True)
            return

        if len(self.game["players"]) <= self.game["mafia"] + 1:
            await interaction.response.send_message("✋ Let more players join.", ephemeral=True)
            return    

        game = self.game
        game["started"] = True

        edited_setup = await interaction.channel.fetch_message(game["game_setup_msg_id"])
        await edited_setup.delete()

        roles = ["Mafia"] * game["mafia"] + ["Townsperson"] * (len(game["players"]) - game["mafia"])
        random.shuffle(roles)

        for player, role in zip(game["players"], roles):
            game["roles"][player.id] = role

        embed = discord.Embed(
            title=f"Mafia - Game Started!",
            description="-# The game has begun! Roles have been assigned. Use the button below to view your role.",
            color=0x0ad919
        )
        embed.add_field(name="Players", value="\n".join(player.mention for player in game["players"]), inline=False)        

        game_msg = await interaction.channel.send(embed=embed, view=ViewRoles(self.bot, game))

        game["game_msg_id"] = game_msg.id

        await interaction.response.defer()

    @discord.ui.button(emoji="🗑️", style=discord.ButtonStyle.gray, custom_id="exitbtn")
    async def _exit(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild

        if interaction.user != self.host:
            await interaction.response.send_message("Only the host can stop the game!", ephemeral=True)
            return

        setup = await interaction.channel.fetch_message(self.game["game_setup_msg_id"])
        await setup.delete()
        del self.bot.games[guild.id]
        await interaction.response.defer()
                
class ViewRoles(View):
    def __init__(self, bot, game):
        super().__init__(timeout=None)
        self.game = game
        self.bot = bot

    @discord.ui.button(label='View Role', style=discord.ButtonStyle.green, custom_id="viewrolebtn")
    async def _viewrole(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = self.game["roles"].get(interaction.user.id, "Role not found")

        user_id = interaction.user.id
        
        if user_id not in self.game["roles"]:
            await interaction.response.send_message("You haven't joined this game.", ephemeral=True)
            return 

        if role == "Mafia":
            msg = "You are a **Murderer**! You must kill everyone without getting caught to win the game."
        elif role == "Townsperson":
            msg = "You are a **Townsperson**! You must catch the murderer(s) before they kill everyone to win the game."
        else:
            msg = "What is your role?"
            
        await interaction.response.send_message(msg, ephemeral=True)

        self.game["viewed_roles"].add(interaction.user.id)

        game_msg = await interaction.channel.fetch_message(self.game["game_msg_id"])
        game_embed = game_msg.embeds[0]
        game_embed.set_field_at(0, name="Players", value="\n".join([f"{player.mention} {'**`[VIEWED ROLE]`**' if player.id in self.game['viewed_roles'] else ''}" for player in self.game["players"]]), inline=False)
        await game_msg.edit(embed=game_embed)

        if len(self.game["viewed_roles"]) == len(self.game["players"]):            
            await game_msg.edit(view=None)
            await self.start_day_phase(interaction.channel, self.game)

    async def start_day_phase(self, channel, game):
        game["phase"] = "day"
        day_phase = discord.Embed(
            title="☀️ Day Phase",
            description="-# Discuss who the murderer might be!",
            color=0xEEE8D0
        )
        day_phase.set_image(url="https://i.ibb.co/cgLG0hT/a5ebb4a1724c6f7723be838042384e93.jpg")
        day_phase.set_footer(text="⏱️ Ends in 20 seconds")
        await channel.send(embed=day_phase)        
        await asyncio.sleep(20)

        await self.start_voting_phase(channel, game)

    async def start_voting_phase(self, channel, game):
        game["phase"] = "voting Time"
        voting = discord.Embed(
            title="⚖️ Voting",
            description="-# Who do you think the murderer is?",
            color=0x857D6A
        )
        voting.set_thumbnail(url="https://i.ibb.co/Ks4D36d/Untitled64-20240727213018.png")
        voting.set_footer(text="⏱️ Ends in 15 seconds")

        vote_msg = await channel.send(embed=voting, view=VotingView(self.bot, game))
        await asyncio.sleep(15)
        await vote_msg.edit(view=None)

        votes = game['votes']
        await self.resolve_voting_phase(channel, game, votes)

    async def resolve_voting_phase(self, channel, game, votes):
        if not votes:
            await channel.send(embed=discord.Embed(description="❌ No votes were cast.", color=0xff4600))
            await self.start_night_phase(channel, game)
            return

        vote_counts = {}
        for voter, votee in votes.items():
            if votee in vote_counts:
                vote_counts[votee] += 1
            else:
                vote_counts[votee] = 1

        max_votes = max(vote_counts.values())
        most_voted_players = [player_id for player_id, count in vote_counts.items() if count == max_votes]

        if len(most_voted_players) > 1:
            await channel.send(embed=discord.Embed(description="⚖️ It's a tie! No one was voted out.", color=0xffcc00))
            await self.start_night_phase(channel, game)
            return

        most_voted_player_id = most_voted_players[0]
        most_voted_player = discord.utils.get(channel.guild.members, id=most_voted_player_id)
        role = game["roles"].get(most_voted_player_id, "Role not found")

        if role == "Mafia":
            game["roles"][most_voted_player_id] = "Ghost_Mafia"
            await channel.send(embed=discord.Embed(description=f"🔪 {most_voted_player.mention} was a Murderer. A murderer has been eliminated!", color=0xff4600))
        else:
            game["roles"][most_voted_player_id] = "Ghost"
            await channel.send(embed=discord.Embed(description=f"💔 {most_voted_player.mention} was not a Murderer.", color=0xff4600))

        await self.assign_ghost_role(most_voted_player)

        remaining_murderers = sum(1 for role in game["roles"].values() if role == "Mafia")
        remaining_townsfolk = sum(1 for role in game["roles"].values() if role not in ["Mafia", "Ghost", "Ghost_Mafia"])

        if remaining_murderers == 0:
            await self.end_game(game, channel, "Civilians")
        elif remaining_townsfolk <= remaining_murderers:
            await self.end_game(game, channel, "Murderer(s)")
        else:
            await self.start_night_phase(channel, game)
        
    async def start_night_phase(self, channel, game):
        game["phase"] = "night"
        night_phase = discord.Embed(
            title="🌖 Night Phase",
            description="-# Murderers, select your target.",
            color=0x3D91E4
        )
        night_phase.set_image(url="https://i.ibb.co/St4bJXG/08ed16834b55bb50bd6381c6fdf4401d.jpg")
        night_phase.set_footer(text="⏱️ Ends in 20 seconds")

        murder_embed = discord.Embed(title="🔪 Murder", description="-# Kill someone!", color=0xAF775C)
        murder_embed.set_thumbnail(url="https://i.ibb.co/9Tf2jkT/Untitled65-20240727213246.png")

        await channel.send(embed=night_phase)
        kill_msg = await channel.send(embed=murder_embed, view=NightView(self.bot, game))
        await asyncio.sleep(20)
        await kill_msg.edit(view=None)
        await self.resolve_night_phase(channel, game)

    async def resolve_night_phase(self, channel, game):
        target_id = game.get("night_target")
        if not target_id:
            await channel.send(embed=discord.Embed(description="❌ The murderers didn't target anyone.", color=0xff4600))
            await self.start_day_phase(channel, game)
            return

        target = discord.utils.get(channel.guild.members, id=target_id)
        if not target:
            await channel.send(embed=discord.Embed(description="🔪 The target could not be found.", color=0xff0000))
            return

        game["roles"][target_id] = "Ghost"
        await self.assign_ghost_role(target)
        await channel.send(embed=discord.Embed(description=f"🔪 {target.mention} was killed during the night.", color=0xff0000))

        remaining_murderers = sum(1 for role in game["roles"].values() if role == "Mafia")
        remaining_townsfolk = sum(1 for role in game["roles"].values() if role not in ["Mafia", "Ghost", "Ghost_Mafia"])

        if remaining_murderers == 0:
            await self.end_game(game, channel, "Civilians")
        elif remaining_townsfolk <= remaining_murderers:
            await self.end_game(game, channel, "Murderer(s)")
        else:
            await self.start_day_phase(channel, game)
    
    async def end_game(self, game, channel, winner):
        guild = channel.guild
        murderers = [member.mention for member in guild.members if member.id in game["roles"] and game["roles"][member.id] in ["Mafia", "Ghost_Mafia"]]

        murderers_list = "\n".join(murderers)

        game_end = discord.Embed(
            title="Game Over",
            description=f"### {winner} 🏆",
            color=0xff0000)

        game_end.add_field(name="Murderers", value=murderers_list, inline=False)

        game_end.set_footer(text="❤️ Thanks for playing!")

        await channel.send(embed=game_end)
        await self.restore_roles(channel, game)
        del self.bot.games[guild.id]

class VotingSelect(discord.ui.Select):
    def __init__(self, bot, game):
        options = [
            discord.SelectOption(label=player.display_name, value=str(player.id))
            for player in game["players"]
            if game["roles"][player.id] not in ["Ghost", "Ghost_Mafia"]
        ]
        super().__init__(placeholder="Vote", min_values=1, max_values=1, options=options)
        self.game = game
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):

        voter_id = interaction.user.id

        if voter_id not in self.game["roles"] or self.game["roles"][voter_id] in ["Ghost", "Ghost_Mafia"]:
            await interaction.response.send_message("You are not allowed to vote.", ephemeral=True)
            return
            
        votee_id = int(self.values[0])
        self.game["votes"][voter_id] = votee_id
        await interaction.response.defer()

class VotingView(View):
    def __init__(self, bot, game):
        super().__init__(timeout=None)
        self.add_item(VotingSelect(bot, game))

class NightSelect(discord.ui.Select):
    def __init__(self, bot, game):
        options = [
            discord.SelectOption(label=player.display_name, value=str(player.id))
            for player in game["players"]
            if game["roles"][player.id] not in ["Ghost", "Ghost_Mafia"]
        ]
        super().__init__(placeholder="Select a target", min_values=1, max_values=1, options=options)
        self.game = game
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        killer_id = interaction.user.id

        if killer_id not in self.game["roles"] or self.game["roles"][killer_id] in ["Ghost_Mafia"]:
            await interaction.response.send_message("You are not allowed to kill.", ephemeral=True)
            return
            
        if self.game["roles"].get(killer_id) == "Mafia":
            target_id = int(self.values[0])
            target_role = self.game["roles"].get(target_id)
            if target_role == "Mafia":
                await interaction.response.send_message("You cannot target another Mafia member.", ephemeral=True)
            else:
                self.game["night_target"] = target_id
                await interaction.response.defer()

        else:
            await interaction.response.send_message("Only murderers can select a target.", ephemeral=True)

class NightView(View):
    def __init__(self, bot, game):
        super().__init__(timeout=20)
        self.add_item(NightSelect(bot, game))

async def setup(bot):
    await bot.add_cog(Mafia(bot))        
