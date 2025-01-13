from discord.ext import commands
import os 

class AutoKicker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = os.environ['WEIRDO']

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.id == self.target_id:
            await member.kick(reason="Auto kicked, don't be concerned about it.")
          
async def setup(bot):
    await bot.add_cog(AutoKicker(bot))
