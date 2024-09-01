# scon/utils/config_manager.py

import json
import os

CONFIG_PATH = "scon_config.json"

def load_config():
    return load_json_file(CONFIG_PATH, {
        "use_sudo": False,
        "container_runtime": "docker"
    })

def save_config(config):
    save_json_file(CONFIG_PATH, config)

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

def set_config(key, value):
    config = load_config()

    if key == "use_sudo":
        config['use_sudo'] = value.lower() == 'true'
        print(f"Set use_sudo to {config['use_sudo']}")
    elif key == "container_runtime":
        if value in ["docker", "podman"]:
            config['container_runtime'] = value
            print(f"Set container_runtime to {config['container_runtime']}")
        else:
            print("Invalid value for container_runtime. Use 'docker' or 'podman'.")
            return
    else:
        print("Invalid configuration key. Use 'use_sudo' or 'container_runtime'.")
        return

    save_config(config)

def show_config():
    config = load_config()
    print("Current configuration:")
    print(f"  use_sudo: {config['use_sudo']}")
    print(f"  container_runtime: {config['container_runtime']}")
