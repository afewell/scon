import subprocess
from scon.utils import json_storage
from datetime import datetime, timedelta
from scon.utils.json_storage import load_config, load_stateful_containers, save_stateful_containers

DEFAULT_MAX_SNAPSHOTS = 5
DEFAULT_RETENTION_DAYS = 30

def handle_snapshot(name):
    config = load_config()
    containers = load_stateful_containers()

    container = next((c for c in containers if c['name'] == name), None)
    if container is None:
        print(f"Stateful container '{name}' not found.")
        return

    snapshot_name = f"{name}_snapshot_{int(time.time())}"
    commit_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} commit {name} {snapshot_name}"
    
    print(f"Creating snapshot for container '{name}' as '{snapshot_name}'...")
    result = subprocess.run(commit_command, shell=True)
    
    if result.returncode == 0:
        tag_choice = input("Do you want to tag this snapshot as important? (y/n): ").strip().lower()
        tagged = tag_choice == 'y'

        container['history'].append({
            "container_id": subprocess.getoutput(f"{config['container_runtime']} ps -q -f name={name}").strip(),
            "timestamp": datetime.utcnow().isoformat(),
            "image": snapshot_name,
            "tagged": tagged
        })

        save_stateful_containers(containers)
        print(f"Snapshot created successfully as '{snapshot_name}'{' (Tagged)' if tagged else ''}")

        # Clean up old untagged snapshots
        cleanup_old_snapshots(name, config.get('max_snapshots', DEFAULT_MAX_SNAPSHOTS))
    else:
        print(f"Failed to create snapshot for container '{name}'")

def cleanup_old_snapshots(container_name, max_snapshots=DEFAULT_MAX_SNAPSHOTS, retention_days=DEFAULT_RETENTION_DAYS):
    containers = load_stateful_containers()
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    container = next((c for c in containers if c['name'] == container_name), None)
    if not container:
        return

    untagged_snapshots = [entry for entry in container['history'] if not entry.get('tagged', False) and entry['image'] != container.get('original_image')]
    old_snapshots = [entry for entry in untagged_snapshots if datetime.fromisoformat(entry['timestamp']) < cutoff_date]

    if len(old_snapshots) > 0:
        for entry in old_snapshots:
            delete_command = f"docker rmi {entry['image']}"
            subprocess.run(delete_command, shell=True)
            container['history'].remove(entry)

        save_stateful_containers(containers)
        print(f"Deleted {len(old_snapshots)} old snapshots for container '{container_name}' that were older than {retention_days} days.")

    if len(untagged_snapshots) > max_snapshots:
        sorted_untagged = sorted(untagged_snapshots, key=lambda x: x['timestamp'])
        to_delete = sorted_untagged[:-max_snapshots]

        for entry in to_delete:
            delete_command = f"docker rmi {entry['image']}"
            subprocess.run(delete_command, shell=True)
            container['history'].remove(entry)

        save_stateful_containers(containers)
        print(f"Deleted {len(to_delete)} old untagged snapshots for container '{container_name}'.")

def docker_container_exists(name):
    config = load_config()
    check_command = f"{config['container_runtime']} ps -a -q -f name={name}"
    container_id = subprocess.getoutput(check_command).strip()
    return bool(container_id)

def get_runtime_command():
    config = load_config()
    return 'sudo ' + config['container_runtime'] if config['use_sudo'] else config['container_runtime']

def check_docker():
    try:
        subprocess.run(["docker", "--version"], check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def handle_create(name, image):
    containers = load_stateful_containers()

    if docker_container_exists(name):
        print(f"A Docker container with the name '{name}' already exists. Please choose a different name.")
        return

    container_entry = create_container_entry(name, image, None)
    containers.append({
        "name": name,
        "containers": [container_entry],
        "snapshots": [],
        "next_snapshot_to_start": None,
        "deleted": []
    })

    save_stateful_containers(containers)
    print(f"Stateful container '{name}' created with base image '{image}'.")

def handle_start(name):
    config = load_config()
    containers = load_stateful_containers()

    container_data = next((c for c in containers if c['name'] == name), None)
    if not container_data:
        print(f"Stateful container '{name}' not found.")
        return

    # Check if a container with this name is already running
    running_container_id = docker_container_exists(name)
    if running_container_id:
        print(f"Error: A Docker container with the name '{name}' already exists.")
        print("Please delete the existing container or choose a different name.")
        return

    # Get the next snapshot to start from
    next_snapshot = container_data['next_snapshot_to_start']
    if not next_snapshot:
        print(f"No snapshot found to start container '{name}'.")
        return

    # Start the new container from the snapshot
    start_command = f"{config['container_runtime']} run -d --name {name} {next_snapshot['image_id']} sleep infinity"
    subprocess.run(start_command, shell=True)

    # Log the new container entry
    container_entry = create_container_entry(name, next_snapshot['image_id'], None)
    container_data['containers'].append(container_entry)
    container_entry['status'] = "running"

    save_stateful_containers(containers)
    print(f"Started container '{name}' from snapshot '{next_snapshot['image_id']}'")

def handle_stop(name):
    config = load_config()
    containers = load_stateful_containers()

    container_data = next((c for c in containers if c['name'] == name), None)
    if not container_data:
        print(f"Stateful container '{name}' not found.")
        return

    container = container_data['containers'][-1]  # Get the latest container

    if container['status'] == "stopped":
        print(f"Container '{name}' is already stopped.")
        return

    # Stop and rename the container
    stop_command = f"{config['container_runtime']} stop {container['container_id']}"
    subprocess.run(stop_command, shell=True)
    container['status'] = "stopped"

    new_name = f"{name}_stopped_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    rename_command = f"{config['container_runtime']} rename {container['container_id']} {new_name}"
    subprocess.run(rename_command, shell=True)

    # Create a snapshot
    snapshot_name = f"{name}_snapshot_{int(time.time())}"
    commit_command = f"{config['container_runtime']} commit {new_name} {snapshot_name}"
    subprocess.run(commit_command, shell=True)

    snapshot_entry = create_snapshot_entry(snapshot_name, snapshot_name)
    container_data['snapshots'].append(snapshot_entry)
    container_data['next_snapshot_to_start'] = snapshot_entry

    save_stateful_containers(containers)
    print(f"Stopped and saved state of '{name}', renamed to '{new_name}'")


def handle_list():
    containers = json_storage.load_stateful_containers()
    if not containers:
        print("No stateful containers found.")
        return

    for container in containers:
        print(f"Stateful Container: {container['name']}")
        print(f"  Current Image: {container['image']}")
        print(f"  History: {container['history']}")

def stop_and_commit_container(name):
    config = load_config()
    containers = load_stateful_containers()

    container = next((c for c in containers if c['name'] == name), None)
    if container is None:
        print(f"Stateful container '{name}' not found.")
        return False

    check_command = f"{config['container_runtime']} ps -q -f name={name}"
    container_id = subprocess.getoutput(check_command).strip()

    if not container_id:
        print(f"No such container: {name}")
        return False

    # Stop the Docker container
    stop_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} stop {name}"
    if subprocess.run(stop_command, shell=True).returncode != 0:
        print(f"Failed to stop container '{name}'")
        return False

    # Rename the stopped container to free up the name
    rename_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} rename {name} {name}_stopped"
    subprocess.run(rename_command, shell=True)

    # Commit the current state of the container before deleting
    new_image_tag = f"{name}_snapshot_{int(time.time())}"
    commit_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} commit {name}_stopped {new_image_tag}"
    if subprocess.run(commit_command, shell=True).returncode == 0:
        container['history'].append({
            "container_id": container_id,
            "timestamp": datetime.utcnow().isoformat(),
            "image": new_image_tag
        })
        save_stateful_containers(containers)
        print(f"Committed snapshot for container '{name}' as '{new_image_tag}'")
        return True
    else:
        print(f"Failed to commit snapshot for container '{name}'")
        return False

def handle_delete(name, option, force=False):
    config = load_config()
    containers = load_stateful_containers()

    container_data = next((c for c in containers if c['name'] == name), None)
    if not container_data:
        print(f"Stateful container '{name}' not found.")
        return

    # First, stop and commit the container as per the stop logic
    stop_and_commit_container(name)

    # Then, delete the container or snapshot based on the selected option
    if option == "entry-only":
        print(f"Deleting stateful container entry '{name}' but retaining local Docker containers and images.")
        container_data['deleted'].append(container_data['containers'][-1])  # Archive the latest container entry
        containers.remove(container_data)

    elif option == "all-snapshots":
        print(f"Deleting all snapshots and the SC entry '{name}'.")
        container_data['deleted'].extend(container_data['snapshots'])  # Archive all snapshots
        containers.remove(container_data)

    elif option == "keep-latest-snapshot":
        print(f"Deleting all but the latest snapshot for stateful container '{name}'.")
        container_data['deleted'].extend(container_data['snapshots'][:-1])  # Archive old snapshots
        container_data['snapshots'] = [container_data['snapshots'][-1]]

    save_stateful_containers(containers)
    print(f"Deleted stateful container '{name}' with option '{option}'.")

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
