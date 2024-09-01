import argparse
from scon.commands import create, start, stop, list_containers, delete, snapshot, config

def main():
    parser = argparse.ArgumentParser(description="Stateful Containers CLI")
    subparsers = parser.add_subparsers(dest='command', required=True)

    create.add_create_command(subparsers)
    start.add_start_command(subparsers)
    stop.add_stop_command(subparsers)
    list_containers.add_list_command(subparsers)
    delete.add_delete_command(subparsers)
    snapshot.add_snapshot_command(subparsers)  # Add this line
    config.add_config_command(subparsers)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
