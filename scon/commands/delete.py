from scon.utils import container_manager

def add_delete_command(subparsers):
    parser = subparsers.add_parser('delete', help='Delete a stateful container entry')
    parser.add_argument('name', help='Name of the stateful container')
    parser.add_argument('option', nargs='?', help='Delete option: entry-only, all-snapshots, keep-latest-snapshot')
    parser.add_argument('--force', action='store_true', help='Force action without confirmation')
    parser.set_defaults(func=handle_delete)

def handle_delete(args):
    # If no option is provided, enter the interactive dialogue
    if not args.option:
        args.option = interactive_delete_dialogue(args.name)
        if not args.option:
            print("Operation cancelled.")
            return
    
    # Proceed with the deletion using the selected option
    container_manager.handle_delete(args.name, args.option, args.force)

def interactive_delete_dialogue(name):
    print(f"You are about to delete the stateful container '{name}'.")
    print("Please select one of the following options:")
    print("1. entry-only: Deletes the stateful container entry but retains all associated Docker containers and images.")
    print("2. all-snapshots: Deletes all snapshots and the stateful container entry.")
    print("3. keep-latest-snapshot: Deletes all snapshots except for the latest one, and deletes the stateful container entry.")
    print("4. Cancel: Abort the deletion process.")

    choice = input("Enter the number corresponding to your choice (1-4): ").strip()

    if choice == '1':
        return 'entry-only'
    elif choice == '2':
        return 'all-snapshots'
    elif choice == '3':
        return 'keep-latest-snapshot'
    elif choice == '4':
        return None
    else:
        print("Invalid choice. Operation cancelled.")
        return None

def delete_container_images(container):
    config = load_config()
    for entry in container['history']:
        delete_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} rmi {entry['image']}"
        subprocess.run(delete_command, shell=True)

def delete_all_but_latest_image(container):
    config = load_config()
    if len(container['history']) > 1:
        for entry in container['history'][:-1]:
            delete_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} rmi {entry['image']}"
            subprocess.run(delete_command, shell=True)

