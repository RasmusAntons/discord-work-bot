import json
from enum import Enum


class ConfKey(Enum):
    DISCORD_TOKEN = 'discord_token'
    MAIN_CHANNEL = 'main_channel'
    WORK_CHANNEL = 'work_channel'
    VOICE_CHANNEL = 'voice_channel'
    AWAKE_COOLDOWN = 'awake_cooldown_h'
    SLEEP_MIN = 'sleep_min_h'
    WORK_DELAY = 'work_delay_h'
    WORK_DURATION = 'work_duration_h'
    REMIND_INTERVAL = 'remind_interval_h'
    BACKGROUND_DELAY = 'background_delay_s'
    MESSAGES = 'messages'
    MARKOV_CHANNELS = 'markov_channels'
    TALK_HOURS = 'talk_hours'
    USERS = 'users'


class MsgKey(Enum):
    AWAKE = 'awake'
    WORKING_TIMER = 'working_timer'
    WORKING_CMD = 'working_cmd'
    ENABLE = 'enable'
    DISABLE = 'disable'
    DONE_TIMER = 'done_timer'
    DONE_CMD = 'done_cmd'
    REMIND = 'remind'
    FAILURE = 'failure'


class Config:
    def __init__(self, filename):
        self.filename = filename
        self.conf = json.load(open(filename))

    def get(self, key: ConfKey):
        return self.conf.get(key.value)

    def get_by_id(self, key):
        return self.conf.get(key)

    def get_msg(self, key: MsgKey):
        return self.conf[ConfKey.MESSAGES.value].get(key.value)

    def get_emoji(self, user_id):
        res = self.conf[ConfKey.USERS.value].get(str(user_id))
        return res['emoji'] if res else None

    def get_name(self, user_id):
        res = self.conf[ConfKey.USERS.value].get(str(user_id))
        return res['name'] if res else None

    def reload(self):
        self.conf = json.load(open(self.filename))
