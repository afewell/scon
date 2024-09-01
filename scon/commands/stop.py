from scon.utils import container_manager

def add_stop_command(subparsers):
    parser = subparsers.add_parser('stop', help='Stop a stateful container and save its state')
    parser.add_argument('name', help='Name of the stateful container')
    parser.add_argument('--force', action='store_true', help='Force action without confirmation')
    parser.set_defaults(func=handle_stop)

def handle_stop(args):
    # Call container_manager.handle_stop with force option
    container_manager.handle_stop(args.name, args.force)
