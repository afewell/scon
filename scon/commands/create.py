from scon.utils import container_manager

def add_create_command(subparsers):
    parser = subparsers.add_parser('create', help='Create a new stateful container')
    parser.add_argument('name', help='Name of the stateful container')
    parser.add_argument('image', help='Initial container image')
    parser.set_defaults(func=handle_create)

def handle_create(args):
    # Check if a Docker container with the same name already exists
    if container_manager.docker_container_exists(args.name):
        print(f"Error: A Docker container with the name '{args.name}' already exists.")
        print(f"Please delete the existing container or choose a different name.")
        print(f"You can list your existing containers with `{container_manager.get_runtime_command()} ps -a`.")
        print(f"To delete an existing container, use `{container_manager.get_runtime_command()} rm {args.name}`.")
        return

    # Proceed with creating the SC if no conflicts
    container_manager.handle_create(args.name, args.image)
