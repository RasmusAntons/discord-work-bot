from tinydb import TinyDB, Query
from tinydb.operations import delete
import time
from enum import Enum
from config import ConfKey


class UserKey(Enum):
    ID = 'id'
    LAST_ACTIVE = 'last_active'
    ENABLED = 'enabled'
    AWAKE = 'awake'
    WORKING = 'working'
    REMIND = 'remind'
    DONE = 'done'
    SLACKING = 'slacking'
    PROMPT = 'prompt'
    AWAKE_COOLDOWN = 'awake_cooldown_h'
    SLEEP_MIN = 'sleep_min_h'
    WORK_DELAY = 'work_delay_h'
    WORK_DURATION = 'work_duration_h'
    REMIND_INTERVAL = 'remind_interval_h'


user_conf = [UserKey.AWAKE_COOLDOWN,
             UserKey.SLEEP_MIN,
             UserKey.WORK_DELAY,
             UserKey.WORK_DURATION,
             UserKey.REMIND_INTERVAL]


class UserState:
    def __init__(self, init=None):
        self.state = init if init is not None else {}

    def set(self, key: UserKey, val):
        self.state[key.value] = val

    def get(self, key: UserKey, default=0):
        r = self.state.get(key.value)
        return r if r is not None else default


class State:
    def __init__(self, config):
        self.config = config
        self.db = TinyDB('state.json')
        self.users = self.db.table('users')
        self.events = self.db.table('events')

    def get_user_key(self, user_id, key: UserKey, default=0):
        user = Query()
        res = self.users.get(user.id == user_id)
        if res:
            val = res.get(key)
            if val is None:
                return self.config.get_by_id(key.value) if key in user_conf else default
            return val
        else:
            return self.config.get_by_id(key.value) if key in user_conf else default

    def set_user_key(self, user_id, key: UserKey, val):
        user = Query()
        if val is not None:
            self.users.upsert({key.value: val}, user.id == user_id)
        else:
            self.users.upsert(delete(key.value), user.id == user_id)

    def get_enabled_users(self):
        user = Query()
        for user in self.users.search(user.enabled == True):
            for key in user_conf:
                if key.value not in user:
                    user[key.value] = self.config.get_by_id(key.value)
            yield UserState(user)

    def update_last_active(self, user_id):
        awoken = False
        user = Query()
        res = UserState(self.users.get(user.id == user_id))
        ts = time.time()
        res.set(UserKey.LAST_ACTIVE, ts)
        if res:
            awake_cooldown = res.get(UserKey.AWAKE_COOLDOWN, self.config.get(ConfKey.AWAKE_COOLDOWN)) * 3600
            sleep_min = res.get(UserKey.SLEEP_MIN, self.config.get(ConfKey.SLEEP_MIN)) * 3600
            if (ts - res.get(UserKey.AWAKE)) > awake_cooldown and (ts - res.get(UserKey.LAST_ACTIVE)) > sleep_min:
                res.set(UserKey.AWAKE, ts)
                awoken = res.get(UserKey.ENABLED)
            self.users.upsert(res.state, user.id == user_id)
        else:
            res.set(UserKey.ID, user_id)
            self.users.insert(res.state)
        return awoken
