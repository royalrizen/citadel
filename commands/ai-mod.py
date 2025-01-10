import discord
from discord.ext import commands
import re
from gemini import Gemini
from utils.staff import is_staff
import config

AI_PROMPT = """
You will be provided moderation action details, and your task is to process them accordingly. First, check if the action is a valid moderation action: `namechange`, `ban`, `kick`, or `timeout`. If the action is not valid, return an error. If the rulebreaker is also a staff member, no action should be taken, and return a message indicating that. If the action is a `timeout`, ensure the timeout duration is provided in `d/h/m` format (e.g., `1d`, `2h`, `30m`). If the timeout duration is invalid or missing, use a default of `1m`. If the action is `namechange`, ensure the new name is valid and provided in the AI response. Finally, return a strict JSON response with the following fields: `status` (success, error, or failed), `message` (any additional details or error messages), `action` (the moderation action performed, such as `ban`, `kick`, `timeout`, or `namechange`), and `timeout` (the duration for timeout actions in `d/h/m` if applicable). Ensure all details are properly validated before proceeding with the action.
"""

class AIMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gemini_key = config.COOKIE

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        if is_staff(message):
            if message.reference and message.reference.message_id:
                match = re.search(r"<@!?(\d+)>", message.content)
                if match:
                    user_id = int(match.group(1))
                    if is_staff(user_id):
                        await message.channel.send(f"{config.ERROR} Can't do it. The user is a staff member.")
                        return

                    action = self.get_action_from_message(message.content)
                    if action:
                        timeout_duration = self.extract_timeout_duration(message.content) if action == "timeout" else None
                        ai_response = self.call_moderation_ai(action, message.author.id, user_id, timeout_duration)

                        if ai_response['status'] == 'success':
                            await message.channel.send(
                                f"👌 **`{action}`** on user **{user_id}** was successful.\n-# {ai_response}"
                            )
                            if action == 'ban':
                                await self.ban_user(message, user_id, ai_response)
                            elif action == 'kick':
                                await self.kick_user(message, user_id, ai_response)
                            elif action == 'timeout':
                                await self.timeout_user(message, user_id, ai_response['timeout'], ai_response)
                            elif action == 'namechange':
                                await self.namechange_user(message, user_id, ai_response)
                        else:
                            await message.channel.send(f"{config.ERROR} {ai_response['message']}")

    def get_action_from_message(self, message_content):
        action_keywords = ['ban', 'kick', 'timeout', 'namechange']
        for keyword in action_keywords:
            if keyword in message_content.lower():
                return keyword
        return None

    def extract_timeout_duration(self, message_content):
        match = re.search(r"(\d+[dhm])", message_content)
        if match:
            return match.group(1)
        return "1m"

    def call_moderation_ai(self, action, mod_id, user_id, timeout=None):
        moderation_details = {
            "action": action,
            "mod_id": mod_id,
            "user_id": user_id,
            "timeout": timeout
        }
        cookies = {"__Secure-1PSID": self.gemini_key}
        prompt_with_details = f"{AI_PROMPT}\n\nModeration Details - {moderation_details}"

        try:
            client = Gemini(cookies=cookies)
            response = client.generate_content(prompt_with_details)
            return response
        except Exception as e:
            return {"status": "error", "message": str(e), "action": action, "timeout": timeout}

    async def ban_user(self, message, user_id, ai_response):
        member = message.guild.get_member(user_id)
        if member:
            await member.ban(reason="Banned by Rizen-AI")
        else:
            await message.channel.send(f"{config.ERROR} User not found in the server.\n-# {ai_response}")

    async def kick_user(self, message, user_id, ai_response):
        member = message.guild.get_member(user_id)
        if member:
            await member.kick(reason="Kicked by Rizen-AI")
        else:
            await message.channel.send(f"{config.ERROR} User not found in the server.\n-# {ai_response}")

    async def timeout_user(self, message, user_id, timeout_duration, ai_response):
        member = message.guild.get_member(user_id)
        if member:
            try:
                await member.timeout_for(timeout_duration, reason="Timed out by RizenAI")
            except discord.errors.Forbidden:
                await message.channel.send(f"{config.ERROR} Bot lacks permission to timeout the user.")
        else:
            await message.channel.send(f"{config.ERROR} User not found in the server.\n-# {ai_response}")

    async def namechange_user(self, message, user_id, ai_response):
        member = message.guild.get_member(user_id)
        if member:
            new_name = ai_response.get('message', None)
            if new_name and len(new_name) <= 32:  # Discord nickname limit
                try:
                    await member.edit(nick=new_name)
                    await message.channel.send(f"👌 Nickname changed to **{new_name}** for user **{user_id}**.")
                except discord.errors.Forbidden:
                    await message.channel.send(f"{config.ERROR} Bot lacks permission to change the nickname.")
            else:
                await message.channel.send(f"{config.ERROR} No valid or too long name suggestion provided.\n-# {ai_response}")
        else:
            await message.channel.send(f"{config.ERROR} User not found in the server.\n-# {ai_response}")

async def setup(bot):
    await bot.add_cog(AIMod(bot))
