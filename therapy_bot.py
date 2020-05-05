import discord
import asyncio
from enum import Enum
from state import State
from markov import Markov
import time
from datetime import datetime
import config
import random


class TherapyBot(discord.Client):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.state = State(config)
        self.markov = Markov(self, config)
        self.prev_talk = 0
        self.expression = None
        self.avatar_backoff = 0
        self.angered = 0

    async def on_ready(self):
        print('I\'m in.')
        await self.markov.talk(self.get_channel(self.config.get_main_channel()))
        self.loop.create_task(self.background_task())

    async def background_task(self):
        while True:
            print("[background loop]")
            for user in self.state.get_enabled_users():
                ts = time.time()
                work_delay = self.state.get_user_conf(user['id'], 'work_delay_h') * 3600
                work_duration = self.state.get_user_conf(user['id'], 'work_duration_h') * 3600
                reminder_interval = self.state.get_user_conf(user['id'], 'remind_interval_h') * 3600
                if user['awake'] > user['working'] and (ts - user['awake']) > work_delay:
                    await self.user_start_working(self.get_user(user['id']))
                elif not user['done'] and (ts - user['working']) > work_duration:
                    await self.user_stop_working(self.get_user(user['id']))
                elif not user['done'] and (ts - user['remind']) > reminder_interval:
                    await self.user_remind_working(self.get_user(user['id']))
            ts = time.time()
            if ts - self.prev_talk > 360 and datetime.now().hour in self.config.get_talk_hours() and datetime.now().minute < 5:
                await self.markov.talk(self.get_channel(self.config.get_main_channel()))
                self.prev_talk = ts
            await self.set_avatar()
            await asyncio.sleep(self.config.get_background_delay())

    async def on_message(self, msg):
        if self.user.id == msg.author.id:
            return
        if self.state.update_last_active(msg.author.id):
            await self.user_awake(msg.author, msg.channel)
        if msg.content.startswith("!markov"):
            cmd = msg.content[7:].strip()
            await self.markov.on_command(msg, cmd)
        if self.user.mentioned_in(msg):
            await self.markov.talk(msg.channel)
        elif msg.content.startswith("!work"):
            cmd = msg.content[5:].strip()
            if cmd == "awake":
                self.state.set_awake(msg.author.id, time.time())
                await self.user_awake(msg.author, msg.channel)
            elif cmd == "start":
                await self.user_start_working(msg.author, 'working_cmd', msg.channel)
            elif cmd == "done":
                await self.user_stop_working(msg.author, 'done_cmd', msg.channel, False)
            elif cmd == "enable":
                self.state.set_enabled(msg.author.id, True)
                await msg.channel.send(self.config.get_message('enable').format(msg.author.mention))
            elif cmd == "disable":
                self.state.set_enabled(msg.author.id, False)
                await msg.channel.send(self.config.get_message('disable').format(msg.author.mention))
            elif cmd.startswith("set"):
                err_msg = f'{msg.author.mention} invalid config key, valid keys are: ' + ', '.join(config.user_settable)
                try:
                    _, key, value = cmd.split(' ')
                    if key in config.user_settable:
                        if value.lower() == 'none':
                            self.state.unset_user_conf(msg.author.id, key)
                            await msg.channel.send(f'{msg.author.mention} ok, unset {key}')
                            return
                        try:
                            value = float(value)
                            self.state.set_user_conf(msg.author.id, key, value)
                            await msg.channel.send(f'{msg.author.mention} ok, set {key} to {value}')
                        except ValueError:
                            await msg.channel.send(f'{msg.author.mention} that\'s not a number!')
                    else:
                        await msg.channel.send(err_msg)
                except ValueError:
                    await msg.channel.send(err_msg)
            elif cmd == "info":
                current = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                last_active = datetime.fromtimestamp(self.state.get_last_active(msg.author.id)).strftime("%Y-%m-%d %H:%M:%S")
                awake = datetime.fromtimestamp(self.state.get_awake(msg.author.id)).strftime("%Y-%m-%d %H:%M:%S")
                working = datetime.fromtimestamp(self.state.get_working(msg.author.id)).strftime("%Y-%m-%d %H:%M:%S")
                res = [
                    f"{msg.author.mention} at {current}:",
                    f"\tenabled: {self.state.get_enabled(msg.author.id)}",
                    f"\tlast active: {last_active}",
                    f"\tawake: {awake}",
                    f"\tworking: {working}",
                    f"\tdone: {self.state.get_done(msg.author.id)}",
                    f"\tconfig:"
                ]
                for key in config.user_settable:
                    res.append(f"\t\t{key}: {self.state.get_user_conf(msg.author.id, key)}")
                await msg.channel.send('\n'.join(res))

    async def on_reaction_add(self, reaction, user):
        msg = reaction.message
        prompt = self.state.get_prompt(user.id)
        done = self.state.get_done(user.id)
        self.state.set_prompt(user.id, 0)
        if prompt == msg.id:
            if reaction.emoji == '\N{WHITE HEAVY CHECK MARK}':
                await msg.add_reaction('<:dreamwuwu:643219778806218773>')
                await self.set_avatar(Expression.HAPPY)
                if done:
                    await msg.channel.send(self.config.get_message('done_cmd').format(user.mention))
                else:
                    self.state.set_slacking(user.id, False)
            elif reaction.emoji == '\N{CROSS MARK}':
                await msg.add_reaction('<:angry_bird:664757860089200650>')
                if done:
                    await msg.channel.send(self.config.get_message('failure').format(user.mention))
                    self.angered = time.time() + 7200
                    await self.set_avatar(Expression.ANGRY)
                else:
                    self.state.set_slacking(user.id, True)
                    await self.set_avatar(Expression.THREATENING)

    async def user_awake(self, user, channel=None):
        ch = channel or self.get_channel(self.config.get_work_channel())
        msg = self.config.get_message('awake')
        work_delay_h = self.state.get_user_conf(user.id, 'work_delay_h')
        await ch.send(msg.format(user.mention, work_delay_h))

    async def user_start_working(self, user, message='working_timer', channel=None):
        ch = channel or self.get_channel(self.config.get_work_channel())
        ts = time.time()
        await ch.send(self.config.get_message(message).format(user.mention))
        self.state.set_working(user.id, ts)
        self.state.set_remind(user.id, ts)
        self.state.set_done(user.id, False)

    async def user_stop_working(self, user, message='done_timer', channel=None, prompt=True):
        ch = channel or self.get_channel(self.config.get_work_channel())
        msg = await ch.send(self.config.get_message(message).format(user.mention))
        if prompt:
            await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')
            await msg.add_reaction('\N{CROSS MARK}')
            self.state.set_prompt(user.id, msg.id)
        else:
            self.state.set_prompt(user.id, 0)
        self.state.set_done(user.id, True)
        self.state.set_slacking(user.id, False)

    async def user_remind_working(self, user):
        ch = self.get_channel(self.config.get_work_channel())
        msg = await ch.send(self.config.get_message('remind').format(user.mention))
        await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')
        await msg.add_reaction('\N{CROSS MARK}')
        self.state.set_prompt(user.id, msg.id)
        self.state.set_remind(user.id, time.time())

    async def set_avatar(self, expression=None):
        print('checking if avatar should change')
        ts = time.time()
        if ts < self.avatar_backoff:
            print(f'waiting {self.avatar_backoff - ts:0.2f} seconds before trying again')
            return
        if expression is None:
            if time.time() < self.angered:
                expression = Expression.ANGRY
            else:
                expression = Expression.HAPPY
                for user in self.state.get_enabled_users():
                    if user['slacking']:
                        expression = Expression.THREATENING
                    elif not user['done'] and expression != Expression.THREATENING:
                        expression = Expression.WORRIED
        if expression != self.expression:
            if self.expression is not None:
                print(f'yes, avatar should change from {self.expression.name} to {expression.name}')
            else:
                print(f'yes, avatar should change to {expression.name}')
            self.expression = expression
            img = f'res/{random.choice(expression.value)}.png'
            with open(img, 'rb') as f:
                dat = f.read()
            try:
                await self.user.edit(avatar=dat)
            except discord.HTTPException:
                print("Cannot set avatar yet")
                self.expression = None
                self.avatar_backoff = time.time() + 600


class Expression(Enum):
    SURPRISED = ['re1a_bikkuri_a1_0', 're1a_bikkuri_a1_1', 're1a_bikkuri_a1_0']
    WORRIED = ['re1a_komaru_a1_0', 're1a_komaru_a1_1', 're1a_komaru_a1_2']
    THREATENING = ['re1a_hig_def_a1_0', 're1a_hig_def_a1_1', 're1a_hig_def_a1_2', 're1a_hig_muhyou_a1_0', 're1a_hig_muhyou_a1_1', 're1a_hig_muhyou_a1_2']
    ANGRY = ['re1a_hig_okoru_a1_0', 're1a_hig_okoru_a1_1', 're1a_hig_okoru_a1_0']
    HAPPY = ['re1a_warai_a1_0', 're1a_warai_a1_1', 're1a_warai_a1_2']
