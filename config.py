import json


class Config:
    def __init__(self, filename):
        self.filename = filename
        self.conf = json.load(open(filename))

    def get_discord_token(self):
        return self.conf['discord']['token']

    def get_main_channel(self):
        return self.conf['main_channel']

    def get_voice_channel(self):
        return self.conf['voice_channel']

    def get_background_delay(self):
        return self.conf['background_delay_s']

    def get_awake_cooldown(self):
        return self.conf['awake_cooldown_h'] * 3600

    def get_sleep_min(self):
        return self.conf['sleep_min_h'] * 3600

    def get_work_delay(self):
        return self.conf['work_delay_h'] * 3600

    def get_work_duration(self):
        return self.conf['work_duration_h'] * 3600

    def get_message(self, key):
        return self.conf['messages'].get(key)

    def reload(self):
        self.conf = json.load(open(self.filename))
