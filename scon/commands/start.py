# scon/commands/start.py

from scon.utils import container_manager

def add_start_command(subparsers):
    parser = subparsers.add_parser('start', help='Start a stateful container')
    parser.add_argument('name', help='Name of the stateful container')
    parser.set_defaults(func=handle_start)

def handle_start(args):
    container_manager.handle_start(args.name)
