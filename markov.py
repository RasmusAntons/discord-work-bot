import markovify
import os
import random
from config import Config, ConfKey
import asyncio


FILENAME = 'markov.json'


class Markov:
    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config
        self.model_all = None
        if os.path.exists(FILENAME):
            with open(FILENAME, 'r') as f:
                self.model_all = markovify.Text.from_json(f.read())

    async def on_command(self, msg, cmd):
        if cmd == "regenerate":
            n = await self.regenerate(msg)
            await msg.channel.send(f"finished regenerating, using {n} messages")

    async def regenerate(self, orig_msg):
        msg_all = []
        n = 0
        for i, channel in enumerate(self.config.get(ConfKey.MARKOV_CHANNELS)):
            await orig_msg.channel.send(f'generating {i + 1}/{len(self.config.get(ConfKey.MARKOV_CHANNELS))}')
            async for msg in self.bot.get_channel(channel).history(limit=10**5):
                if not msg.author.bot:
                    n += 1
                    text = msg.content
                    msg_all.append(text)
        self.model_all = markovify.NewlineText('\n'.join(msg_all))
        await orig_msg.channel.send('compiling...')
        self.model_all = self.model_all.compile(inplace=True)
        with open(FILENAME, 'w') as f:
            f.write(self.model_all.to_json())
        return n

    async def talk(self, channel):
        if self.model_all is None:
            return
        keep_talking = True
        while keep_talking:
            for i in range(100):
                m = self.model_all.make_sentence()
                if m:
                    await channel.trigger_typing()
                    await asyncio.sleep(0.04 * len(m))
                    await channel.send(m)
                    break
            keep_talking = bool(random.getrandbits(1))
