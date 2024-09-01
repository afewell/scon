use clap::{Arg, Command};
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::process::Command as ProcessCommand;
use chrono::{DateTime, Utc};

#[derive(Serialize, Deserialize)]
struct Config {
    use_sudo: bool,
    container_runtime: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct HistoryEntry {
    container_id: String,
    timestamp: DateTime<Utc>,
    image: String,
}

#[derive(Serialize, Deserialize)]
struct StatefulContainer {
    name: String,
    image: String,
    history: Vec<HistoryEntry>,
}

fn check_docker() -> bool {
    match ProcessCommand::new("docker").arg("--version").output() {
        Ok(output) => output.status.success(),
        Err(_) => false,
    }
}

fn handle_create(name: &str, image: &str) {
    if !check_docker() {
        eprintln!("Docker is not available on this system. Please ensure Docker is installed and try again.");
        return;
    }

    let mut containers = load_stateful_containers();

    if containers.iter().any(|c| c.name == name) {
        eprintln!("A stateful container with the name '{}' already exists.", name);
        return;
    }

    let container = StatefulContainer {
        name: name.to_string(),
        image: image.to_string(),
        history: vec![],
    };

    containers.push(container);
    save_stateful_containers(&containers);

    println!("Created stateful container '{}'", name);
}

fn load_stateful_containers() -> Vec<StatefulContainer> {
    let containers_path = "stateful_containers.json";
    let containers_data = fs::read_to_string(containers_path).unwrap_or_else(|_| "[]".to_string());
    serde_json::from_str(&containers_data).unwrap_or_else(|_| vec![])
}

fn save_stateful_containers(containers: &Vec<StatefulContainer>) {
    let containers_path = "stateful_containers.json";
    let containers_data = serde_json::to_string_pretty(containers).unwrap();
    let mut file = OpenOptions::new()
        .write(true)
        .truncate(true)
        .create(true)
        .open(containers_path)
        .unwrap();
    file.write_all(containers_data.as_bytes()).unwrap();
}

fn load_config() -> Config {
    let config_path = "scon_config.json";
    let config_data = fs::read_to_string(config_path).unwrap_or_else(|_| {
        let default_config = Config {
            use_sudo: false,
            container_runtime: "docker".to_string(),
        };
        save_config(&default_config);
        serde_json::to_string(&default_config).unwrap()
    });
    serde_json::from_str(&config_data).unwrap()
}

fn save_config(config: &Config) {
    let config_path = "scon_config.json";
    let config_data = serde_json::to_string_pretty(config).unwrap();
    let mut file = OpenOptions::new()
        .write(true)
        .truncate(true)
        .create(true)
        .open(config_path)
        .unwrap();
    file.write_all(config_data.as_bytes()).unwrap();
}

fn handle_config_set(key: &str, value: &str) {
    let mut config = load_config();

    match key {
        "use_sudo" => {
            match value.parse::<bool>() {
                Ok(parsed_value) => {
                    config.use_sudo = parsed_value;
                    println!("Set use_sudo to {}", config.use_sudo);
                }
                Err(_) => {
                    eprintln!("Invalid value for use_sudo. Please use 'true' or 'false'.");
                    return;
                }
            }
        }
        "container_runtime" => {
            if value == "docker" || value == "podman" {
                config.container_runtime = value.to_string();
                println!("Set container_runtime to {}", config.container_runtime);
            } else {
                eprintln!("Invalid value for container_runtime. Use 'docker' or 'podman'.");
                return;
            }
        }
        _ => {
            eprintln!("Invalid configuration key. Use 'use_sudo' or 'container_runtime'.");
            return;
        }
    }

    save_config(&config);
}

fn handle_config_show() {
    let config = load_config();
    println!("Current configuration:");
    println!("  use_sudo: {}", config.use_sudo);
    println!("  container_runtime: {}", config.container_runtime);
}

fn handle_start(name: &str) {
    let config = load_config();
    let mut containers = load_stateful_containers();

    if let Some(container) = containers.iter_mut().find(|c| c.name == name) {
        // Check if a container with this name is already running
        let check_command = format!("{} ps -q -f name={}", config.container_runtime, name);
        let output = ProcessCommand::new("sh").arg("-c").arg(&check_command).output().unwrap();
        let running_container_id = String::from_utf8_lossy(&output.stdout).trim().to_string();

        if !running_container_id.is_empty() {
            // Check if the running container ID is in the history
            if let Some(history_entry) = container.history.iter().find(|entry| entry.container_id == running_container_id) {
                if history_entry.container_id == running_container_id {
                    println!("The container is already running with the most recent version.");
                    return;
                } else {
                    // Interactive dialogue for user to decide what to do with the running container
                    // (Implement this based on your interactive dialogue strategy)
                }
            } else {
                eprintln!("A container with this name is already running but is not recognized by 'scon'. Please stop or rename it.");
                return;
            }
        }

        let command = if config.use_sudo {
            format!("sudo {} run -d --name {} {} sleep infinity", config.container_runtime, name, container.image)
        } else {
            format!("{} run -d --name {} {} sleep infinity", config.container_runtime, name, container.image)
        };

        println!("Starting stateful container '{}'", name);
        if let Ok(output) = ProcessCommand::new("sh").arg("-c").arg(&command).output() {
            let container_id = String::from_utf8_lossy(&output.stdout).trim().to_string();
            container.history.push(HistoryEntry {
                container_id: container_id.clone(),
                timestamp: Utc::now(),
                image: container.image.clone(),
            });
            save_stateful_containers(&containers);
        } else {
            eprintln!("Failed to start container '{}'", name);
        }            
    } else {
        eprintln!("Stateful container '{}' not found.", name);
    }
}

fn handle_stop(name: &str) {
    let config = load_config();
    let mut containers = load_stateful_containers();

    if let Some(container) = containers.iter_mut().find(|c| c.name == name) {
        // Check if the container is running
        let check_command = format!("{} ps -a --filter name={} --format '{{{{.ID}}}}'", config.container_runtime, name);
        let container_id = ProcessCommand::new("sh").arg("-c").arg(&check_command).output().unwrap();

        if container_id.stdout.is_empty() {
            eprintln!("No such container: {}", name);
            return;
        }

        let stop_command = if config.use_sudo {
            format!("sudo {} stop {}", config.container_runtime, name)
        } else {
            format!("{} stop {}", config.container_runtime, name)
        };

        println!("Stopping stateful container '{}'", name);
        if let Err(e) = ProcessCommand::new("sh").arg("-c").arg(&stop_command).status() {
            eprintln!("Failed to stop container '{}': {}", name, e);
            return;
        }

        let new_image_tag = format!("{}:v{}", container.name, container.history.len() + 1);
        let commit_command = if config.use_sudo {
            format!("sudo {} commit {} {}", config.container_runtime, name, new_image_tag)
        } else {
            format!("{} commit {} {}", config.container_runtime, name, new_image_tag)
        };

        println!("Saving state of '{}'", name);
        if let Err(e) = ProcessCommand::new("sh").arg("-c").arg(&commit_command).status() {
            eprintln!("Failed to save state: {}", e);
        } else {
            container.history.push(HistoryEntry {
                container_id: String::from_utf8_lossy(&container_id.stdout).trim().to_string(),
                timestamp: Utc::now(),
                image: new_image_tag.clone(),
            });
            save_stateful_containers(&containers);
        }
    } else {
        eprintln!("Stateful container '{}' not found.", name);
    }
}

fn handle_list() {
    let containers = load_stateful_containers();
    if containers.is_empty() {
        println!("No stateful containers found.");
    } else {
        for container in containers {
            println!("Stateful Container: {}", container.name);
            println!("  Current Image: {}", container.image);
            println!("  History: {:?}", container.history);
        }
    }
}

enum DeleteOptions {
    EntryOnly,
    AllSnapshots,
    KeepLatestSnapshot,
}

fn handle_delete(name: &str, options: DeleteOptions) {
    let config = load_config();
    let mut containers = load_stateful_containers();

    if let Some(index) = containers.iter().position(|c| c.name == name) {
        let container = &containers[index];

        // Check if the container is running
        let check_command = format!("{} ps -q -f name={}", config.container_runtime, name);
        let output = ProcessCommand::new("sh").arg("-c").arg(&check_command).output().unwrap();
        let running_container_id = String::from_utf8_lossy(&output.stdout).trim().to_string();

        if !running_container_id.is_empty() {
            eprintln!("Cannot delete stateful container '{}' because it is still running. Please stop it first.", name);
            return;
        }

        // Handle different delete options
        match options {
            DeleteOptions::EntryOnly => {
                println!("Deleting stateful container entry '{}' but retaining local images.", name);
                containers.remove(index);
            }
            DeleteOptions::AllSnapshots => {
                println!("Deleting all snapshot images for stateful container '{}'.", name);
                // Delete all history except the base image
                // Use appropriate Docker command to delete images
            }
            DeleteOptions::KeepLatestSnapshot => {
                println!("Deleting all but the most recent snapshot for stateful container '{}'.", name);
                // Delete all history except the latest snapshot and base image
                // Use appropriate Docker command to delete images
            }
        }

        save_stateful_containers(&containers);
    } else {
        eprintln!("Stateful container '{}' not found.", name);
    }
}

fn main() {
    let matches = Command::new("scon")
        .version("1.0")
        .about("Stateful Containers CLI")
        .subcommand_required(true)  // Ensure at least one subcommand is required
        .arg_required_else_help(true)  // Show help if no arguments are provided
        .subcommand(
            Command::new("create")
                .about("Create a new stateful container")
                .arg(Arg::new("name")
                    .help("Name of the stateful container")
                    .required(true))
                .arg(Arg::new("image")
                    .help("Initial container image")
                    .required(true)),
        )
        .subcommand(
            Command::new("start")
                .about("Start a stateful container")
                .arg(Arg::new("name")
                    .help("Name of the stateful container")
                    .required(true)),
        )
        .subcommand(
            Command::new("stop")
                .about("Stop a stateful container and save its state")
                .arg(Arg::new("name")
                    .help("Name of the stateful container")
                    .required(true)),
        )
        .subcommand(
            Command::new("list")
                .about("List all stateful containers"),
        )
        .subcommand(
            Command::new("delete")
                .about("Delete a stateful container entry")
                .arg(Arg::new("name")
                    .help("Name of the stateful container")
                    .required(true))
                .arg(Arg::new("option")
                    .help("Delete option: entry-only, all-snapshots, keep-latest-snapshot")
                    .required(false)),
        )
        .subcommand(
            Command::new("config")
                .about("Configure scon settings")
                .subcommand(
                    Command::new("set")
                        .about("Set a configuration value")
                        .arg(Arg::new("key")
                            .help("Configuration key (use_sudo or container_runtime)")
                            .required(true))
                        .arg(Arg::new("value")
                            .help("Value to set for the configuration key")
                            .required(true)),
                )
                .subcommand(
                    Command::new("show")
                        .about("Show the current configuration"),
                ),
        )
        .get_matches();

    if let Some(matches) = matches.subcommand_matches("create") {
        let name = matches.get_one::<String>("name").unwrap();
        let image = matches.get_one::<String>("image").unwrap();
        handle_create(name, image);
    }

    if let Some(matches) = matches.subcommand_matches("start") {
        let name = matches.get_one::<String>("name").unwrap();
        handle_start(name);
    }

    if let Some(matches) = matches.subcommand_matches("stop") {
        let name = matches.get_one::<String>("name").unwrap();
        handle_stop(name);
    }

    if let Some(_) = matches.subcommand_matches("list") {
        handle_list();
    }

    if let Some(matches) = matches.subcommand_matches("delete") {
        let name = matches.get_one::<String>("name").unwrap();
        let option = matches.get_one::<String>("option").map(|s| s.as_str());

        let delete_option = match option {
            Some("entry-only") => DeleteOptions::EntryOnly,
            Some("all-snapshots") => DeleteOptions::AllSnapshots,
            Some("keep-latest-snapshot") => DeleteOptions::KeepLatestSnapshot,
            _ => {
                eprintln!("Invalid or missing delete option. Use 'entry-only', 'all-snapshots', or 'keep-latest-snapshot'.");
                return;
            }
        };

        handle_delete(name, delete_option);
    }

    if let Some(matches) = matches.subcommand_matches("config") {
        if let Some(set_matches) = matches.subcommand_matches("set") {
            let key = set_matches.get_one::<String>("key").unwrap();
            let value = set_matches.get_one::<String>("value").unwrap();
            handle_config_set(key, value);
        } else if let Some(_) = matches.subcommand_matches("show") {
            handle_config_show();
        }
    }
}