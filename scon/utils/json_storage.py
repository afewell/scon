# scon/utils/json_storage.py

import json
import os

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
