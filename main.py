import argparse
from config import Config
from therapy_bot import TherapyBot


def run_bot(config):
    disc = TherapyBot(config)
    disc.loop.run_until_complete(disc.login(config.get_discord_token()))
    disc.loop.run_until_complete(disc.connect())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', '-c', type=str, default='config.json', help='config json')
    args = parser.parse_args()
    run_bot(Config(args.config))
