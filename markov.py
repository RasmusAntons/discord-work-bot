import markovify
import os
import random
from config import Config, ConfKey
import asyncio


FILENAME = 'markov/{}.json'
TXT_FILE = 'markov/{}.txt'


class Markov:
    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config
        self.models = {}

    async def load_models(self):
        work_channel = self.config.get(ConfKey.WORK_CHANNEL)
        keys = ['all']
        for member in self.bot.get_channel(work_channel).members:
            if not member.bot:
                keys.append(member.id)
        for key in keys:
            fn = FILENAME.format(key)
            if os.path.exists(fn):
                with open(fn, 'r') as f:
                    self.models[key] = markovify.Text.from_json(f.read())

    async def on_command(self, msg, cmd):
        if cmd == "regenerate":
            n = await self.regenerate(msg)
            await msg.channel.send(f"finished regenerating, using {n} messages")
        elif cmd == "regenerate keep":
            n = await self.regenerate(msg, keep=True)
            await msg.channel.send(f"finished regenerating, using {n} messages")
        elif cmd.startswith("imitate "):
            name = cmd[8:]
            for id_str, info in self.config.get(ConfKey.USERS):
                if info['name'] == name:
                    await self.talk(msg.channel, user=int(id_str))
                    break

    async def regenerate(self, orig_msg, keep=False):
        msgs = {'all': []}
        n = 0
        for i, channel in enumerate(self.config.get(ConfKey.MARKOV_CHANNELS)):

            if keep:
                keys = ['all']
                work_channel = self.config.get(ConfKey.WORK_CHANNEL)
                for member in self.bot.get_channel(work_channel).members:
                    if not member.bot:
                        keys.append(member.id)
                for key in keys:
                    fn = TXT_FILE.format(key)
                    if os.path.exists(fn):
                        with open(fn, 'r') as f:
                            msgs[key] = f.read().split('\n')
            else:
                await orig_msg.channel.send(f'reading channel {i + 1}/{len(self.config.get(ConfKey.MARKOV_CHANNELS))}')
                async for msg in self.bot.get_channel(channel).history(limit=10**5):
                    if not msg.author.bot:
                        n += 1
                        text = msg.content
                        msgs['all'].append(text)
                        if msg.author.id not in msgs:
                            msgs[msg.author.id] = [text]
                        else:
                            msgs[msg.author.id].append(text)
        for key, texts in msgs.items():
            if not keep:
                with open(TXT_FILE.format(key)) as f:
                    f.write('\n'.join(texts))
            model = markovify.NewlineText('\n'.join(texts), retain_original=False)
            self.models[key] = model.compile(inplace=True)
            with open(FILENAME.format(key), 'w') as f:
                f.write(self.models[key].to_json())
        return n

    async def talk(self, channel, user='all', cont_chance=0.5):
        model = self.models.get(user)
        if model is None:
            return
        keep_talking = True
        while keep_talking:
            for i in range(100):
                m = model.make_sentence()
                if m:
                    await channel.trigger_typing()
                    await asyncio.sleep(0.04 * len(m))
                    await channel.send(m)
                    break
            keep_talking = random.random() < cont_chance
