import json
import os
from datetime import timedelta

DEFAULT_RETENTION_DAYS = 30
CONTAINERS_PATH = "stateful_containers.json"
CONFIG_PATH = "scon_config.json"

def load_json_file(path, default_data):
    if os.path.exists(path):
        with open(path, 'r') as file:
            return json.load(file)
    else:
        with open(path, 'w') as file:
            json.dump(default_data, file, indent=4)
        return default_data

def save_json_file(path, data):
    with open(path, 'w') as file:
        json.dump(data, file, indent=4)

def load_stateful_containers():
    return load_json_file(CONTAINERS_PATH, [])

def save_stateful_containers(containers):
    save_json_file(CONTAINERS_PATH, containers)

def load_config():
    return load_json_file(CONFIG_PATH, {
        "use_sudo": False,
        "container_runtime": "docker"
    })

def save_config(config):
    save_json_file(CONFIG_PATH, config)

def handle_snapshot(name):
    # Previous snapshot creation code...
    tag_choice = input("Do you want to tag this snapshot as important? (y/n): ").strip().lower()
    tagged = tag_choice == 'y'

    container['history'].append({
        "container_id": subprocess.getoutput(f"{config['container_runtime']} ps -q -f name={name}").strip(),
        "timestamp": datetime.utcnow().isoformat(),
        "image": snapshot_name,
        "tagged": tagged
    })

    json_storage.save_stateful_containers(containers)
    print(f"Snapshot created successfully as '{snapshot_name}'{' (Tagged)' if tagged else ''}")

    # Clean up old untagged snapshots
    cleanup_old_snapshots(name, config.get('max_snapshots', DEFAULT_MAX_SNAPSHOTS))

def cleanup_old_snapshots(container_name, max_snapshots=DEFAULT_MAX_SNAPSHOTS, retention_days=DEFAULT_RETENTION_DAYS):
    containers = json_storage.load_stateful_containers()
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    container = next((c for c in containers if c['name'] == container_name), None)
    if not container:
        return

    untagged_snapshots = [entry for entry in container['history'] if not entry.get('tagged', False)]
    old_snapshots = [entry for entry in untagged_snapshots if datetime.fromisoformat(entry['timestamp']) < cutoff_date]

    if len(old_snapshots) > 0:
        for entry in old_snapshots:
            delete_command = f"docker rmi {entry['image']}"
            subprocess.run(delete_command, shell=True)
            container['history'].remove(entry)

        json_storage.save_stateful_containers(containers)
        print(f"Deleted {len(old_snapshots)} old snapshots for container '{container_name}' that were older than {retention_days} days.")

    # Also enforce the max snapshot limit after time-based cleanup
    if len(untagged_snapshots) > max_snapshots:
        sorted_untagged = sorted(untagged_snapshots, key=lambda x: x['timestamp'])
        to_delete = sorted_untagged[:-max_snapshots]

        for entry in to_delete:
            delete_command = f"docker rmi {entry['image']}"
            subprocess.run(delete_command, shell=True)
            container['history'].remove(entry)

        json_storage.save_stateful_containers(containers)
        print(f"Deleted {len(to_delete)} old untagged snapshots for container '{container_name}'.")