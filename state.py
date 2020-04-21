from tinydb import TinyDB, Query
from tinydb.operations import delete
import time


default_user = {'last_active': 0, 'enabled': False, 'awake': 0, 'working': 0, 'remind': 0, 'done': False}


class State:
    def __init__(self, config):
        self.config = config
        self.db = TinyDB('state.json')
        self.users = self.db.table('users')
        self.events = self.db.table('events')

    def get_user_attr(self, user_id, key, default=0):
        user = Query()
        res = self.users.get(user.id == user_id)
        if res:
            try:
                return res.get(key)
            except KeyError:
                self.set_user_attr(user_id, key, default_user[key])
                return default_user[key]
        else:
            return default

    def get_last_active(self, user_id):
        return self.get_user_attr(user_id, 'last_active')

    def get_awake(self, user_id):
        return self.get_user_attr(user_id, 'awake')

    def get_working(self, user_id):
        return self.get_user_attr(user_id, 'working')

    def get_done(self, user_id):
        return self.get_user_attr(user_id, 'done')

    def get_enabled(self, user_id):
        return self.get_user_attr(user_id, 'enabled')

    def get_remind(self, user_id):
        return self.get_user_attr(user_id, 'remind')

    def get_prompt(self, user_id):
        return self.get_user_attr(user_id, 'prompt')

    def get_user_conf(self, user_id, key):
        res = self.get_user_attr(user_id, 'conf_' + key)
        return res or self.config.get(key)

    def set_user_attr(self, user_id, key, value):
        user = Query()
        self.users.update({key: value}, user.id == user_id)

    def set_working(self, user_id, ts):
        self.set_user_attr(user_id, 'working', ts)

    def set_done(self, user_id, done):
        self.set_user_attr(user_id, 'done', done)

    def set_enabled(self, user_id, enabled):
        self.set_user_attr(user_id, 'enabled', enabled)

    def set_remind(self, user_id, ts):
        self.set_user_attr(user_id, 'remind', ts)

    def set_prompt(self, user_id, message_id):
        self.set_user_attr(user_id, 'prompt', message_id)

    def set_user_conf(self, user_id, key, value):
        self.set_user_attr(user_id, 'conf_' + key, value)

    def unset_user_conf(self, user_id, key):
        user = Query()
        self.users.update(delete('conf_' + key), user.id == user_id)

    def get_enabled_users(self):
        user = Query()
        for user in self.users.search(user.enabled == True):
            res = default_user.copy()
            res.update(user)
            yield res

    def update_last_active(self, user_id):
        awoken = False
        user = Query()
        res = self.users.get(user.id == user_id)
        ts = time.time()
        obj = {'last_active': ts}
        if res:
            awake_cooldown = self.get_user_conf(user_id, 'awake_cooldown_h') * 3600
            sleep_min = self.get_user_conf(user_id, 'sleep_min_h') * 3600
            if (ts - (res['awake'] or 0)) > awake_cooldown and (ts - res['last_active']) > sleep_min:
                obj['awake'] = ts
                awoken = res['enabled']
            self.users.update(obj, user.id == user_id)
        else:
            obj['id'] = user_id
            self.users.insert(obj)
        return awoken
