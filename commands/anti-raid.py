import discord
from discord.ext import commands
from utils.staff import is_staff
import config 

class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="massban", aliases=['mb'], usage="<message>", description="Mass bans all the users who sent a specific message. Use it during raids.")
    async def mass_ban(self, ctx, *, target_message: str):
        """Bans users who sent a certain message."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        m = await ctx.send("🔎 Scanning messages... Please wait.")
        matching_users = set() 
        async for message in ctx.channel.history(limit=None): 
            if message.content == target_message:
                matching_users.add((message.author.id, str(message.author)))

        if not matching_users:
            await ctx.send(f"{config.ERROR} No users found who sent that message.")
            return

        await m.delete()

        embed = discord.Embed(
            title="Mass Ban Confirmation",
            description="\n".join([f"`{username}` ({user_id})" for user_id, username in matching_users]),
            color=config.SECONDARY_COLOR
        )

        confirmation_message = await ctx.send(embed=embed)
        await confirmation_message.add_reaction(config.SUCCESS)
        await confirmation_message.add_reaction(config.ERROR)

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in [config.SUCCESS, config.ERROR]
                and reaction.message.id == confirmation_message.id
            )

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
            await confirmation_message.clear_reactions()
        except asyncio.TimeoutError:
            await ctx.send("Confirmation timed out. No action taken.")
            return

        if str(reaction.emoji) == config.ERROR:
            await ctx.send("Mass ban canceled.")
            return

        banned_count = 0
        for user_id, _ in matching_users:
            try:
                await ctx.guild.ban(discord.Object(id=user_id), reason="Raid")
                banned_count += 1
            except discord.Forbidden:
                await ctx.send(f"Failed to ban user with ID `{user_id}` (missing permissions).")
            except discord.HTTPException:
                await ctx.send(f"Failed to ban user with ID `{user_id}` (HTTP error).")

        await ctx.send(f"Successfully banned **{banned_count}** users.")

async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
