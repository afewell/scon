from scon.utils import json_storage
import subprocess
from datetime import datetime

DEFAULT_MAX_SNAPSHOTS = 5
DEFAULT_RETENTION_DAYS = 30

def handle_snapshot(name):
    config = json_storage.load_config()
    containers = json_storage.load_stateful_containers()

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

        json_storage.save_stateful_containers(containers)
        print(f"Snapshot created successfully as '{snapshot_name}'{' (Tagged)' if tagged else ''}")

        # Clean up old untagged snapshots
        cleanup_old_snapshots(name, config.get('max_snapshots', DEFAULT_MAX_SNAPSHOTS))
    else:
        print(f"Failed to create snapshot for container '{name}'")

def cleanup_old_snapshots(container_name):
    config = json_storage.load_config()
    max_snapshots = config.get('max_snapshots', DEFAULT_MAX_SNAPSHOTS)
    retention_days = config.get('retention_days', DEFAULT_RETENTION_DAYS)
    
    containers = json_storage.load_stateful_containers()
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    container = next((c for c in containers if c['name'] == container_name), None)
    if not container:
        return

    # Filter out tagged snapshots and the original image
    untagged_snapshots = [entry for entry in container['history'] if not entry.get('tagged', False) and entry['image'] != container.get('original_image')]
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
    if not check_docker():
        print("Docker is not available on this system. Please ensure Docker is installed and try again.")
        return

    containers = json_storage.load_stateful_containers()

    if any(c['name'] == name for c in containers):
        print(f"A stateful container with the name '{name}' already exists.")
        return

    container = {
        "name": name,
        "image": image,
        "original_image": args.image,
        "history": []
    }

    containers.append(container)
    json_storage.save_stateful_containers(containers)
    print(f"Stateful container '{args.name}' created with base image '{args.image}'")

def handle_start(name):
    config = load_config()
    containers = load_stateful_containers()

    # Check if the SC exists
    container = next((c for c in containers if c['name'] == name), None)
    if container is None:
        print(f"Stateful container '{name}' not found.")
        return

    # Check if a Docker container with the same name already exists
    if docker_container_exists(name):
        print(f"Error: A Docker container with the name '{name}' already exists.")
        print(f"Please delete the existing container or choose a different name.")
        print(f"You can list your existing containers with `{get_runtime_command()} ps -a`.")
        print(f"To delete an existing container, use `{get_runtime_command()} rm {name}`.")
        return

    # Start the new container from the latest snapshot
    command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} run -d --name {name} {container['image']} sleep infinity"
    container_id = subprocess.getoutput(command).strip()

    container['history'].append({
        "container_id": container_id,
        "timestamp": datetime.utcnow().isoformat(),
        "image": container['image']
    })
    save_stateful_containers(containers)
    print(f"Started stateful container '{name}'")

def handle_stop(name, force=False):
    config = load_config()
    containers = load_stateful_containers()

    container = next((c for c in containers if c['name'] == name), None)
    if container is None:
        print(f"Stateful container '{name}' not found.")
        return

    check_command = f"{config['container_runtime']} ps -a --filter name={name} --format '{{{{.ID}}}}'"
    container_id = subprocess.getoutput(check_command).strip()

    if not container_id:
        print(f"No such container: {name}")
        return

    if not force:
        confirmation = input(f"Are you sure you want to stop the container '{name}'? This action will save its state. (y/n): ").lower()
        if confirmation != 'y' and confirmation != 'yes':
            print("Operation aborted.")
            return

    # Stop the Docker container
    stop_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} stop {name}"
    if subprocess.run(stop_command, shell=True).returncode != 0:
        print(f"Failed to stop container '{name}'")
        return

    # Commit the container to a new image snapshot
    new_image_tag = f"{container['name']}:v{len(container['history']) + 1}"
    commit_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} commit {name} {new_image_tag}"
    if subprocess.run(commit_command, shell=True).returncode != 0:
        print(f"Failed to save state of '{name}'")
        return

    # Rename the stopped Docker container to free up the name
    new_container_name = f"{name}_stopped_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    rename_command = f"{'sudo ' if config['use_sudo'] else ''}{config['container_runtime']} rename {name} {new_container_name}"
    if subprocess.run(rename_command, shell=True).returncode != 0:
        print(f"Failed to rename the container '{name}'")
        return

    container['history'].append({
        "container_id": container_id,
        "timestamp": datetime.utcnow().isoformat(),
        "image": new_image_tag
    })
    save_stateful_containers(containers)
    print(f"Stopped and saved state of '{name}', renamed to '{new_container_name}'")

def handle_list():
    containers = json_storage.load_stateful_containers()
    if not containers:
        print("No stateful containers found.")
        return

    for container in containers:
        print(f"Stateful Container: {container['name']}")
        print(f"  Current Image: {container['image']}")
        print(f"  History: {container['history']}")

def handle_delete(name, option, force=False):
    config = load_config()
    containers = load_stateful_containers()

    # Locate the SC
    container_index = next((i for i, c in enumerate(containers) if c['name'] == name), None)
    if container_index is None:
        print(f"Stateful container '{name}' not found.")
        return

    container = containers[container_index]

    # Use the force option to skip confirmation
    if not force:
        confirmation = input(f"Are you sure you want to delete the SC '{name}'? This action cannot be undone. (y/n): ").lower()
        if confirmation != 'y' and confirmation != 'yes':
            print("Operation aborted.")
            return

    if option == "entry-only":
        print(f"Deleting stateful container entry '{name}' but retaining local Docker containers and images.")
        containers.pop(container_index)

    elif option == "all-snapshots":
        print(f"Deleting all snapshots and the SC entry '{name}'.")
        delete_container_images(container)
        containers.pop(container_index)

    elif option == "keep-latest-snapshot":
        print(f"Deleting all but the latest snapshot for stateful container '{name}'.")
        delete_all_but_latest_image(container)
        containers.pop(container_index)

    # Save the updated state of containers
    save_stateful_containers(containers)
    print(f"Deleted stateful container '{name}'")

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
