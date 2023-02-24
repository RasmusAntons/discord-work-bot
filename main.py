import argparse
from config import Config, ConfKey
from therapy_bot import TherapyBot


def run_bot(config):
    disc = TherapyBot(config)
    disc.run(config.get(ConfKey.DISCORD_TOKEN))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', '-c', type=str, default='config.json', help='config json')
    args = parser.parse_args()
    run_bot(Config(args.config))
