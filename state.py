from tinydb import TinyDB, Query
import time


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
            return res[0].get(key)
        else:
            return default

    def get_last_active(self, user_id):
        return self.get_user_attr(user_id, 'last_active')

    def get_awake(self, user_id):
        return self.get_user_attr(user_id, 'awake')

    def get_working(self, user_id):
        return self.get_user_attr(user_id, 'working')

    def get_enabled(self, user_id):
        return self.get_user_attr(user_id, 'enabled')

    def set_user_attr(self, user_id, key, value):
        user = Query()
        self.users.update({key: value}, user.id == user_id)

    def set_working(self, user_id, ts):
        self.set_user_attr(user_id, 'working', ts)

    def set_enabled(self, user_id, enabled):
        self.set_user_attr(user_id, 'enabled', enabled)

    def get_enabled_users(self):
        user = Query()
        return self.users.search(user.enabled)

    def update_last_active(self, user_id):
        awoken = False
        user = Query()
        res = self.users.get(user.id == user_id)
        ts = time.time()
        obj = {'last_active': ts}
        if res:
            if (ts - res['awake']) > self.config.get_awake_cooldown() and (ts - res['last_active']) > self.config.get_sleep_min():
                obj['awake'] = ts
                awoken = res['enabled']
            self.users.update(obj, user.id == user_id)
        else:
            obj['id'] = user_id
            obj['enabled'] = False
            obj['awake'] = 0
            obj['working'] = 0
            self.users.insert(obj)
        return awoken
