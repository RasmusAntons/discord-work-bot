import discord
import asyncio
from enum import Enum
from state import State, UserKey, user_conf
from markov import Markov
from config import Config, ConfKey, MsgKey
import time
from datetime import datetime
from queue import Queue
import random
import os


class TherapyBot(discord.Client):
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.state = State(config)
        self.markov = Markov(self, config)
        self.prev_talk = 0
        self.expression = None # todo: actual avatar
        self.avatar_backoff = 0
        self.angered = 0
        self.guessing_prompt = None
        self.guessing_target = None
        self.guesses = []
        self.guessing_blocked = False
        self.audio_queue = Queue()

    async def on_ready(self):
        print('I\'m in.')
        await self.markov.load_models()
        # await self.markov.talk(self.get_channel(self.config.get(ConfKey.MAIN_CHANNEL)))
        self.loop.create_task(self.background_task())

    async def background_task(self):
        while True:
            for user in self.state.get_enabled_users():
                ts = time.time()
                work_delay = user.get(UserKey.WORK_DELAY) * 3600
                work_duration = user.get(UserKey.WORK_DURATION) * 3600
                reminder_interval = user.get(UserKey.REMIND_INTERVAL) * 3600
                user_id = user.get(UserKey.ID)
                discord_user = self.get_user(user_id) or await self.fetch_user(user_id)
                if user.get(UserKey.AWAKE) > user.get(UserKey.WORKING) and (ts - user.get(UserKey.AWAKE)) > work_delay:
                    await self.user_start_working(discord_user)
                elif not user.get(UserKey.DONE) and (ts - user.get(UserKey.WORKING)) > work_duration:
                    await self.user_stop_working(discord_user)
                elif not user.get(UserKey.DONE) and (ts - user.get(UserKey.REMIND)) > reminder_interval:
                    await self.user_remind_working(discord_user)
            ts = time.time()
            if ts - self.prev_talk > 360 and datetime.now().hour in self.config.get(ConfKey.TALK_HOURS) and datetime.now().minute < 5:
                await self.markov.talk(self.get_channel(self.config.get(ConfKey.MAIN_CHANNEL)))
                self.prev_talk = ts
            await self.set_avatar()
            await asyncio.sleep(self.config.get(ConfKey.BACKGROUND_DELAY))

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
        elif msg.content == "!gg":
            if not self.guessing_blocked:
                await self.start_guessing_game(msg.channel)
        elif msg.content.startswith("!testmsg "):
            _, msg_id, usr_name = msg.content.split(' ')
            msg_key = MsgKey(msg_id)
            usr_id = 0
            for id_str, info in self.config.get(ConfKey.USERS).items():
                if info['name'] == usr_name:
                    usr_id = int(id_str)
                    break
            else:
                await msg.channel.send('I don\'t know who that is')
            name_first = msg_key in [MsgKey.FAILURE, MsgKey.DONE_TIMER, MsgKey.REMIND]
            delay = 3 if msg_key == MsgKey.FAILURE else (1 if msg_key in [MsgKey.DONE_TIMER, MsgKey.REMIND] else 0)
            await self.play_message_snd(msg_key, usr_id, name_first, delay)
        elif msg.content.startswith("!work"):
            cmd = msg.content[5:].strip()
            if cmd == "awake":
                self.state.set_user_key(msg.author.id, UserKey.AWAKE, time.time())
                await self.user_awake(msg.author, msg.channel)
            elif cmd == "start":
                await self.user_start_working(msg.author, MsgKey.WORKING_CMD, msg.channel)
            elif cmd == "done":
                await self.user_stop_working(msg.author, MsgKey.DONE_CMD, msg.channel, False)
            elif cmd == "enable":
                self.state.set_user_key(msg.author.id, UserKey.ENABLED, True)
                await msg.channel.send(self.config.get_msg(MsgKey.ENABLE).format(msg.author.mention))
            elif cmd == "disable":
                self.state.set_user_key(msg.author.id, UserKey.ENABLED, False)
                await msg.channel.send(self.config.get_msg(MsgKey.DISABLE).format(msg.author.mention))
            elif cmd.startswith("set"):
                err_msg = f'{msg.author.mention} invalid config key, valid keys are: ' + ', '.join([e.value for e in user_conf])
                try:
                    _, key, value = cmd.split(' ')
                    key: UserKey = UserKey(key)
                    if value.lower() == 'none':
                        self.state.set_user_key(msg.author.id, key.value, None)
                        await msg.channel.send(f'{msg.author.mention} ok, unset {key.value}')
                        return
                    try:
                        value = float(value)
                        self.state.set_user_key(msg.author.id, key, value)
                        await msg.channel.send(f'{msg.author.mention} ok, set {key.value} to {value}')
                    except ValueError:
                        await msg.channel.send(f'{msg.author.mention} that\'s not a number!')
                except ValueError:
                    await msg.channel.send(err_msg)
            elif cmd == "info":
                current = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                last_active = datetime.fromtimestamp(self.state.get_user_key(msg.author.id, UserKey.LAST_ACTIVE)).strftime("%Y-%m-%d %H:%M:%S")
                awake = datetime.fromtimestamp(self.state.get_user_key(msg.author.id, UserKey.AWAKE)).strftime("%Y-%m-%d %H:%M:%S")
                working = datetime.fromtimestamp(self.state.get_user_key(msg.author.id, UserKey.WORKING)).strftime("%Y-%m-%d %H:%M:%S")
                res = [
                    f"{msg.author.mention} at {current}:",
                    f"\tenabled: {self.state.get_user_key(msg.author.id, UserKey.ENABLED)}",
                    f"\tlast active: {last_active}",
                    f"\tawake: {awake}",
                    f"\tworking: {working}",
                    f"\tdone: {self.state.get_user_key(msg.author.id, UserKey.DONE)}",
                    f"\tconfig:"
                ]
                for key in user_conf:
                    res.append(f"\t\t{key.value}: {self.state.get_user_key(msg.author.id, key)}")
                await msg.channel.send('\n'.join(res))

    async def on_reaction_add(self, reaction, user):
        if user.id == self.user.id:
            return
        msg = reaction.message
        prompt = self.state.get_user_key(user.id, UserKey.PROMPT)
        done = self.state.get_user_key(user.id, UserKey.DONE)
        if prompt:
            self.state.set_user_key(user.id, UserKey.PROMPT, 0)
        if prompt == msg.id:
            if reaction.emoji == '\N{WHITE HEAVY CHECK MARK}':
                await msg.add_reaction('<:dreamwuwu:643219778806218773>')
                await self.set_avatar()
                if done:
                    await msg.channel.send(self.config.get_msg(MsgKey.DONE_CMD).format(user.mention))
                else:
                    self.state.set_user_key(user.id, UserKey.SLACKING, False)
            elif reaction.emoji == '\N{CROSS MARK}':
                await msg.add_reaction('<:angry_bird:664757860089200650>')
                if done:
                    await self.set_avatar(Expression.ANGRY)
                    await msg.channel.send(self.config.get_msg(MsgKey.FAILURE).format(user.mention))
                    await self.play_message_snd(MsgKey.FAILURE, user.id, True, 3)
                    self.angered = time.time() + 7200
                else:
                    self.state.set_user_key(user.id, UserKey.SLACKING, True)
                    await self.set_avatar(Expression.THREATENING)
        elif self.guessing_prompt == msg.id:
            if user.id not in self.guesses:
                for uid_str, info in self.config.get(ConfKey.USERS).items():
                    if str(reaction.emoji) == info['emoji']:
                        if self.guessing_target == int(uid_str):
                            self.guessing_prompt = None
                            self.guessing_blocked = False
                            discord_user = self.get_user(self.guessing_target) or await self.fetch_user(self.guessing_target)
                            await msg.channel.send(f'{user.mention} won the guessing game by guessing {discord_user.display_name}')
                        else:
                            self.guesses.append(user.id)
                            await msg.channel.send(f'{user.mention} guessed wrong')
                        break

    async def user_awake(self, user, channel=None):
        ch = channel or self.get_channel(self.config.get(ConfKey.WORK_CHANNEL))
        msg = self.config.get_msg(MsgKey.AWAKE)
        work_delay_h = self.state.get_user_key(user.id, UserKey.WORK_DELAY)
        await ch.send(msg.format(user.mention, work_delay_h))
        await self.play_message_snd(MsgKey.AWAKE, user.id)

    async def user_start_working(self, user, message=MsgKey.WORKING_TIMER, channel=None):
        ch = channel or self.get_channel(self.config.get(ConfKey.WORK_CHANNEL))
        ts = time.time()
        self.state.set_user_key(user.id, UserKey.WORKING, ts)
        self.state.set_user_key(user.id, UserKey.REMIND, ts)
        self.state.set_user_key(user.id, UserKey.DONE, False)
        await self.set_avatar()
        await ch.send(self.config.get_msg(message).format(user.mention))
        await self.play_message_snd(message, user.id)

    async def user_stop_working(self, user, message=MsgKey.DONE_TIMER, channel=None, prompt=True):
        ch = channel or self.get_channel(self.config.get(ConfKey.WORK_CHANNEL))
        self.state.set_user_key(user.id, UserKey.DONE, True)
        self.state.set_user_key(user.id, UserKey.SLACKING, False)
        await self.set_avatar()
        msg = await ch.send(self.config.get_msg(message).format(user.mention))
        if prompt:
            await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')
            await msg.add_reaction('\N{CROSS MARK}')
            self.state.set_user_key(user.id, UserKey.PROMPT, msg.id)
        else:
            self.state.set_user_key(user.id, UserKey.PROMPT, 0)
        await self.play_message_snd(message, user.id, message == MsgKey.DONE_TIMER, 1 if (message == MsgKey.DONE_TIMER) else 0)

    async def user_remind_working(self, user):
        ch = self.get_channel(self.config.get(ConfKey.WORK_CHANNEL))
        msg = await ch.send(self.config.get_msg(MsgKey.REMIND).format(user.mention))
        await msg.add_reaction('\N{WHITE HEAVY CHECK MARK}')
        await msg.add_reaction('\N{CROSS MARK}')
        self.state.set_user_key(user.id, UserKey.PROMPT, msg.id)
        self.state.set_user_key(user.id, UserKey.REMIND, time.time())
        await self.play_message_snd(MsgKey.REMIND, user.id, True, 1)

    async def start_guessing_game(self, channel=None):
        if channel is None:
            channel = self.get_channel(self.config.get(ConfKey.MAIN_CHANNEL))
        users = self.config.get(ConfKey.USERS)
        uid_str = random.choice(list(users.keys()))
        self.guessing_target = int(uid_str)
        self.guesses = []
        msg = await channel.send("Starting guessing game!")
        self.guessing_prompt = msg.id
        self.guessing_blocked = True
        infos = list(users.values())
        random.shuffle(infos)
        for info in infos:
            await msg.add_reaction(info['emoji'])
        for i in range(5):
            await asyncio.sleep(20)
            if self.guessing_prompt is None:
                break
            await self.markov.talk(channel, user=self.guessing_target, cont_chance=0)
        else:
            self.guessing_blocked = False

    async def set_avatar(self, expression=None):
        ts = time.time()
        if ts < self.avatar_backoff:
            print(f'waiting {self.avatar_backoff - ts:0.2f} seconds before trying again')
            return
        if time.time() < self.angered:
            expression = Expression.ANGRY
        elif expression is None:
            expression = Expression.HAPPY
            for user in self.state.get_enabled_users():
                if user.get(UserKey.SLACKING):
                    expression = Expression.THREATENING
                elif not user.get(UserKey.DONE) and expression != Expression.THREATENING:
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
                await asyncio.sleep(2)
            except discord.HTTPException:
                print("Cannot set avatar yet")
                self.expression = None
                self.avatar_backoff = time.time() + 600

    async def play_message_snd(self, msg: MsgKey, usr_id=None, name_first=False, delay=0):
        usr_name = self.config.get_name(usr_id)
        ch = self.get_channel(self.config.get(ConfKey.VOICE_CHANNEL))
        for member in ch.members:
            if member.id == usr_id:
                break
        else:
            return
        msg_opts = []
        i = 0
        while os.path.exists(f'res/{msg.value}_{i}.wav'):
            msg_opts.append(f'res/{msg.value}_{i}.wav')
            i += 1
        init = self.audio_queue.empty()
        if not name_first:
            self.audio_queue.put(random.choice(msg_opts))
            if usr_name is not None:
                if delay:
                    self.audio_queue.put(delay)
                self.audio_queue.put(f'res/{usr_name}.wav')
        else:
            if usr_name is not None:
                self.audio_queue.put(f'res/{usr_name}.wav')
                if delay:
                    self.audio_queue.put(delay)
            self.audio_queue.put(random.choice(msg_opts))
        self.audio_queue.put(1)
        if init:
            for old_vc in self.voice_clients:
                old_vc: discord.VoiceClient
                if old_vc.is_connected():
                    vc = old_vc
                    break
            else:
                vc = await ch.connect()

            def on_complete(err):
                if not self.audio_queue.empty():
                    e = self.audio_queue.get()
                    if type(e) == int:
                        time.sleep(e)
                        on_complete(None)
                    else:
                        vc.play(discord.FFmpegPCMAudio(e), after=on_complete)
                else:
                    asyncio.run_coroutine_threadsafe(vc.disconnect(), vc.loop)
            await asyncio.sleep(1)
            vc.play(discord.FFmpegPCMAudio(self.audio_queue.get()), after=on_complete)


class Expression(Enum):
    SURPRISED = ['re1a_bikkuri_a1_0', 're1a_bikkuri_a1_1', 're1a_bikkuri_a1_0']
    WORRIED = ['re1a_komaru_a1_0', 're1a_komaru_a1_1', 're1a_komaru_a1_2']
    THREATENING = ['re1a_hig_def_a1_0', 're1a_hig_def_a1_1', 're1a_hig_def_a1_2', 're1a_hig_muhyou_a1_0', 're1a_hig_muhyou_a1_1', 're1a_hig_muhyou_a1_2']
    ANGRY = ['re1a_hig_okoru_a1_0', 're1a_hig_okoru_a1_1', 're1a_hig_okoru_a1_0']
    HAPPY = ['re1a_warai_a1_0', 're1a_warai_a1_1', 're1a_warai_a1_2']
