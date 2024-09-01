use clap::{Arg, Command};
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::process::Command as ProcessCommand;

#[derive(Serialize, Deserialize)]
struct Config {
    use_sudo: bool,
    container_runtime: String,
}

#[derive(Serialize, Deserialize)]
struct StatefulContainer {
    name: String,
    image: String,
    history: Vec<String>,
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
        history: vec![image.to_string()],
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
    let containers = load_stateful_containers();

    if let Some(container) = containers.iter().find(|c| c.name == name) {
        let command = if config.use_sudo {
            format!("sudo {} run -d {} sleep infinity", config.container_runtime, container.image)
        } else {
            format!("{} run -d {} sleep infinity", config.container_runtime, container.image)
        };

        println!("Starting stateful container '{}'", name);
        if let Err(e) = ProcessCommand::new("sh").arg("-c").arg(&command).status() {
            eprintln!("Failed to start container '{}': {}", name, e);
        }
    } else {
        eprintln!("Stateful container '{}' not found.", name);
    }
}

fn handle_stop(name: &str) {
    let config = load_config();
    let mut containers = load_stateful_containers();

    if let Some(container) = containers.iter_mut().find(|c| c.name == name) {
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

        let new_image_tag = format!("{}:{}", container.image, container.history.len() + 1);
        let commit_command = if config.use_sudo {
            format!("sudo {} commit {} {}", config.container_runtime, name, new_image_tag)
        } else {
            format!("{} commit {} {}", config.container_runtime, name, new_image_tag)
        };

        println!("Saving state of '{}'", name);
        if let Err(e) = ProcessCommand::new("sh").arg("-c").arg(&commit_command).status() {
            eprintln!("Failed to save state: {}", e);
        } else {
            container.history.push(new_image_tag);
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

fn main() {
    let matches = Command::new("scon")
        .version("1.0")
        .about("Stateful Containers CLI")
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

    if let Some(matches) = matches.subcommand_matches("config") {
        if let Some(set_matches) = matches.subcommand_matches("set") {
            let key = set_matches.get_one::<String>("key").unwrap();
            let value = set_matches.get_one::<String>("value").unwrap();
            handle_config_set(key, value);
        } else if let Some(_) = matches.subcommand_matches("show") {
            handle_config_show();
        }
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
    
}
