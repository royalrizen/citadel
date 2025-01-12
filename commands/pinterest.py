import discord
from discord.ext import commands
import os
import requests
from bs4 import BeautifulSoup
import urllib.parse
import config

class Pinterest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    def get_pinterest_images(self, keyword):
        encoded_keyword = urllib.parse.quote(keyword)
        url = f'https://in.pinterest.com/search/pins/?rs=typed&q={encoded_keyword}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.content, 'html.parser')
        link_tags = soup.find_all('link', href=True)
        img_urls = []
        for link in link_tags:
            href = link.get('href')
            if href and (href.endswith('.jpg') or href.endswith('.jpeg') or href.endswith('.png')):
                img_urls.append(href)
        return img_urls

    @commands.command(name="pinterest", aliases=['pins'], usage="<keyword>", description="Search for images on Pinterest")
    async def pinterest(self, ctx, *, keyword: str):
        m = await ctx.send("📌 Searching on **Pinterest**...")
        try:
            image_urls = self.get_pinterest_images(keyword)
            if image_urls:
                batch_size = 10
                for i in range(0, len(image_urls), batch_size):
                    await ctx.send("\n".join(image_urls[i:i + batch_size]))
            else:
                await ctx.send(f"No images found for **{keyword}**.")
            await m.delete()
        except Exception as e:
            await ctx.send(f"{config.ERROR} {e}")

async def setup(bot):
    await bot.add_cog(Pinterest(bot))
