# scon/commands/list_containers.py

from scon.utils import container_manager

def add_list_command(subparsers):
    parser = subparsers.add_parser('list', help='List all stateful containers')
    parser.set_defaults(func=handle_list)

def handle_list(args):
    container_manager.handle_list()
