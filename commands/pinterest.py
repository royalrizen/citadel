import discord
from discord.ext import commands
from pinscrape import scraper
import os
import config

class PinScrape(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.output_folder = "cache" 
        self.proxies = {}  # leaving it for now
        self.number_of_workers = 10
        os.makedirs(self.output_folder, exist_ok=True)

    @commands.command(name="pinterest", aliases=['pins'], usage="<keyword>", description="Search for images on Pinterest")
    async def pinterest(self, ctx, *, keyword: str):
        await ctx.trigger_typing()

        try:
            images_to_download = 9
            details = scraper.scrape(
                keyword=keyword,
                output_folder=self.output_folder,
                proxies=self.proxies,
                number_of_workers=self.number_of_workers,
                images_to_download=images_to_download
            )

            if details["isDownloaded"]:
                image_paths = details["urls_list"]
                files = []

                for image_path in image_paths:
                    full_path = os.path.join(self.output_folder, image_path)
                    if os.path.exists(full_path):
                        files.append(discord.File(full_path))

                batch_size = 10
                for i in range(0, len(files), batch_size):
                    await ctx.send(f"🔎 **{keyword}**:", files=files[i:i + batch_size])

                for image_path in image_paths:
                    full_path = os.path.join(self.output_folder, image_path)
                    if os.path.exists(full_path):
                        os.remove(full_path)
            else:
                await ctx.send(f"No images found for **{keyword}**.")
        except Exception as e:
            await ctx.send(f"{config.ERROR} {e}")

async def setup(bot):
    await bot.add_cog(PinScrape(bot))
