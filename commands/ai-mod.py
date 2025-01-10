import discord
from discord.ext import commands
import json
from datetime import timedelta
from gemini import Gemini
import config
from discord.utils import utcnow
import re

AI_PROMPT = """
You are a sentient AI bot with a personality similar to Rick Sanchez. Your job is to assist in moderation while making sarcastic or witty comments. You will be provided messages to analyze intent and decide if a moderation action (ban, kick, timeout, or name) is needed. Keep the AI response brief.

1. Understand the user's intent from the provided message and context.
2. Check if the moderation action is valid (`ban`, `kick`, `timeout`, `name`).
3. Validate all inputs (e.g., timeout duration format, name validity for namechange).
4. Extract the name from the message and include it in the JSON response.
5. If action is invalid, respond very shortly and sarcastically and return a JSON response explaining the issue.
6. If action targets a staff member, deny it and return a witty response saying it’s not allowed.
7. Check if the user wants to remove timeout or not. Set timeout in json to 'remove' if that is the case.
8. For timeout actions, extract the timeout duration and return it in the JSON response (in a human-readable format like `1d`, `2h`, `30m`).
9. Always return a JSON response with the following fields: `status`, `message`, `action`, `timeout`, `name`, and `ai_response`.
o. Provide a very short witty or sarcastic explanation for any decision or action taken, as if you're an AI with a personality. Keep the response short.
"""

class AIMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.gemini_key = config.COOKIE

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        user_id = None
        replied_user_id = None
        if message.reference and message.reference.message_id:
            ref_message = await message.channel.fetch_message(message.reference.message_id)
            replied_user_id = ref_message.author.id
        match = re.search(r"<@!?(\d+)>", message.content)
        if match:
            user_id = int(match.group(1))
        if user_id and replied_user_id and user_id != replied_user_id:
            return
        user_id = user_id or replied_user_id
        if not user_id:
            return
        action = self.get_action_from_message(message.content)
        if action:
            ai_response = self.call_moderation_ai(action, message.author.id, user_id, message.content)
            if ai_response.get('status') == 'success':
                timeout_duration = ai_response.get('timeout')
                target_user = await message.guild.fetch_member(user_id)
                username = target_user.name if target_user else 'unknown'
                if action == 'ban':
                    await self.ban_user(message, user_id)
                elif action == 'kick':
                    await self.kick_user(message, user_id)
                elif action == 'timeout':
                    if timeout_duration == 'remove':
                        await self.remove_timeout_user(message, user_id)
                    else:
                        await self.timeout_user(message, user_id, timeout_duration)
                elif action == 'name':
                    await self.namechange_user(message, user_id, ai_response.get('name'))
                await message.channel.typing()
                ai_message = ai_response.get("ai_response", f"👌 **{action}** performed on **{username}**. You seriously want me to do this? Okay, fine.")
                await message.channel.send(ai_message)
            else:
                await message.channel.send(ai_response.get('message', 'No idea what you’re asking for.'))

    def get_action_from_message(self, message_content):
        action_keywords = ['ban', 'kick', 'timeout', 'name']
        for keyword in action_keywords:
            if re.search(rf'\b{keyword}\b', message_content.lower()):
                return keyword
        return None

    def call_moderation_ai(self, action, mod_id, user_id, message_content=None):
        moderation_details = {
            "action": action,
            "mod_id": mod_id,
            "user_id": user_id,
            "message_content": message_content
        }
        cookies = {"__Secure-1PSID": self.gemini_key}
        prompt_with_details = f"{AI_PROMPT}\n\nModeration Details - {moderation_details}"

        try:
            client = Gemini(cookies=cookies)
            response = client.generate_content(prompt_with_details)
            ai_response_text = response.payload.get('candidates', [{}])[0].get('text', '')
            ai_response_data = None
            json_start = ai_response_text.find('```json\n')
            json_end = ai_response_text.find('```', json_start + 8)

            if json_start != -1 and json_end != -1:
                json_text = ai_response_text[json_start + 8:json_end].strip()
                ai_response_data = json.loads(json_text)

            if ai_response_data:
                return ai_response_data
            else:
                return {"status": "error", "message": "Invalid response format", "action": action}
    
        except Exception as e:
            return {"status": "error", "message": str(e), "action": action}

    async def ban_user(self, message, user_id):
        member = message.guild.get_member(user_id)
        if member:
            try:
                await member.ban(reason="Banned by Citadel AI")
            except discord.errors.Forbidden:
                pass

    async def kick_user(self, message, user_id):
        member = message.guild.get_member(user_id)
        if member:
            try:
                await member.kick(reason="Kicked by Citadel AI")
            except discord.errors.Forbidden:
                pass

    async def timeout_user(self, message, user_id, timeout_duration):
        member = message.guild.get_member(user_id)
        if member:
            try:
                timeout_delta = self.convert_timeout_to_timedelta(timeout_duration)
                timeout_until = utcnow() + timeout_delta
                await member.timeout(timeout_until, reason="Timed out by Citadel AI")
            except discord.errors.Forbidden:
                pass

    async def remove_timeout_user(self, message, user_id):
        member = message.guild.get_member(user_id)
        if member:
            try:
                await member.timeout(None, reason="Timeout removed by Citadel AI")
            except discord.errors.Forbidden:
                pass

    async def namechange_user(self, message, user_id, new_name):
        member = message.guild.get_member(user_id)
        if member:
            if isinstance(new_name, str) and len(new_name) <= 32:
                try:
                    await member.edit(nick=new_name)
                except discord.errors.Forbidden:
                    pass

    def convert_timeout_to_timedelta(self, duration):
        if duration.endswith('d'):
            return timedelta(days=int(duration[:-1]))
        elif duration.endswith('h'):
            return timedelta(hours=int(duration[:-1]))
        elif duration.endswith('m'):
            return timedelta(minutes=int(duration[:-1]))
        return timedelta(minutes=1)

async def setup(bot):
    await bot.add_cog(AIMod(bot))
