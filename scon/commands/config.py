# scon/commands/config.py

from scon.utils import config_manager

def add_config_command(subparsers):
    parser = subparsers.add_parser('config', help='Configure scon settings')
    config_subparsers = parser.add_subparsers(dest='config_command', required=True)

    parser_config_set = config_subparsers.add_parser('set', help='Set a configuration value')
    parser_config_set.add_argument('key', help='Configuration key (use_sudo or container_runtime)')
    parser_config_set.add_argument('value', help='Value to set for the configuration key')
    parser_config_set.set_defaults(func=handle_config_set)

    parser_config_show = config_subparsers.add_parser('show', help='Show the current configuration')
    parser_config_show.set_defaults(func=handle_config_show)

def handle_config_set(args):
    config_manager.set_config(args.key, args.value)

def handle_config_show(args):
    config_manager.show_config()
