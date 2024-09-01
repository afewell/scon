import subprocess
import time
from datetime import datetime
from scon.utils import json_storage

def add_snapshot_command(subparsers):
    parser = subparsers.add_parser('snapshot', help='Manually create a snapshot of a running container')
    parser.add_argument('name', help='Name of the stateful container')
    parser.set_defaults(func=handle_snapshot)

def handle_snapshot(args):
    config = json_storage.load_config()
    containers = json_storage.load_stateful_containers()

    container = next((c for c in containers if c['name'] == args.name), None)
    if container is None:
        print(f"Stateful container '{args.name}' not found.")
        return

    snapshot_name = f"{args.name}_snapshot_{int(time.time())}"
    commit_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} commit {args.name} {snapshot_name}"
    
    print(f"Creating snapshot for container '{args.name}' as '{snapshot_name}'...")
    result = subprocess.run(commit_command, shell=True)
    
    if result.returncode == 0:
        container['history'].append({
            "container_id": subprocess.getoutput(f"{config['container_runtime']} ps -q -f name={args.name}").strip(),
            "timestamp": datetime.utcnow().isoformat(),
            "image": snapshot_name
        })
        json_storage.save_stateful_containers(containers)
        print(f"Snapshot created successfully as '{snapshot_name}'")
    else:
        print(f"Failed to create snapshot for container '{args.name}'")
