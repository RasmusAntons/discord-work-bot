import discord
import asyncio
from state import State
import time


class TherapyBot(discord.Client):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.state = State(config)

    async def on_ready(self):
        print('I\'m in.')
        self.loop.create_task(self.background_task())

    async def background_task(self):
        while True:
            for user in self.state.get_enabled_users():
                ts = time.time()
                if user['awake'] > user['working'] and (ts - user['awake']) > self.config.get_work_delay():
                    await self.user_start_working(self.get_user(user['id']))
                elif user['working'] > 0 and (ts - user['working']) > self.config.get_work_duration():
                    await self.user_stop_working(self.get_user(user['id']))
            await asyncio.sleep(self.config.get_background_delay())

    async def on_message(self, msg):
        if self.user.id == msg.author.id:
            return
        if self.state.update_last_active(msg.author.id):
            await self.user_awake(msg.author, msg.channel)
        if msg.content.startswith("!work"):
            cmd = msg.content[5:].strip()
            if cmd == "start":
                await self.user_start_working(msg.author, 'working_cmd', msg.channel)
            elif cmd == "done":
                await self.user_stop_working(msg.author, 'done_cmd', msg.channel)
            elif cmd == "enable":
                self.state.set_enabled(msg.author.id, True)
                await msg.channel.send(self.config.get_message('enable').format(msg.author.mention))
            elif cmd == "disable":
                self.state.set_enabled(msg.author.id, False)
                await msg.channel.send(self.config.get_message('disable').format(msg.author.mention))

    async def user_awake(self, user, channel=None):
        ch = channel or self.get_channel(self.config.get_main_channel())
        msg = self.config.get_message('awake')
        await ch.send(msg.format(user.mention))

    async def user_start_working(self, user, message='working_timer', channel=None):
        ch = channel or self.get_channel(self.config.get_main_channel())
        await ch.send(self.config.get_message(message).format(user.mention))
        self.state.set_working(user.id, time.time())

    async def user_stop_working(self, user, message='done_timer', channel=None):
        ch = channel or self.get_channel(self.config.get_main_channel())
        await ch.send(self.config.get_message(message).format(user.mention))
        self.state.set_working(user.id, 0)
