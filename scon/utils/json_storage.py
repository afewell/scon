import json
import os
from platformdirs import PlatformDirs

DEFAULT_RETENTION_DAYS = 30
DEFAULT_MAX_SNAPSHOTS = 5

# Get the appropriate directory for configuration and data files
dirs = PlatformDirs("scon", "YourCompanyName")

CONFIG_PATH = os.path.join(dirs.user_config_dir, "scon_config.json")
CONTAINERS_PATH = os.path.join(dirs.user_data_dir, "stateful_containers.json")

# Ensure directories exist
os.makedirs(dirs.user_config_dir, exist_ok=True)
os.makedirs(dirs.user_data_dir, exist_ok=True)

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
        "container_runtime": "docker",
        "max_snapshots": DEFAULT_MAX_SNAPSHOTS,
        "retention_days": DEFAULT_RETENTION_DAYS
    })

def save_config(config):
    save_json_file(CONFIG_PATH, config)

# Container and Snapshot structures
def create_container_entry(name, image, container_id):
    return {
        "name": name,
        "container_id": container_id,
        "image": image,
        "created_at": datetime.utcnow().isoformat(),
        "status": "created"
    }

def create_snapshot_entry(name, image_id):
    return {
        "name": name,
        "image_id": image_id,
        "created_at": datetime.utcnow().isoformat()
    }
