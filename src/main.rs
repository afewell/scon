use clap::{Arg, Command};
use serde::{Deserialize, Serialize};
use std::fs::{self, OpenOptions};
use std::io::Write;

#[derive(Serialize, Deserialize)]
struct StatefulContainer {
    name: String,
    image: String,
    history: Vec<String>,
}

fn handle_create(name: &str, image: &str) {
    let mut containers = load_containers();

    if containers.iter().any(|c| c.name == name) {
        eprintln!("A container with the name '{}' already exists.", name);
        return;
    }

    let container = StatefulContainer {
        name: name.to_string(),
        image: image.to_string(),
        history: vec![image.to_string()],
    };

    containers.push(container);
    save_containers(&containers);

    println!("Created stateful container '{}'", name);
}

fn load_containers() -> Vec<StatefulContainer> {
    let config_path = "scon_config.json";
    let config_data = fs::read_to_string(config_path).unwrap_or_else(|_| "[]".to_string());
    serde_json::from_str(&config_data).unwrap_or_else(|_| vec![])
}

fn save_containers(containers: &Vec<StatefulContainer>) {
    let config_path = "scon_config.json";
    let config_data = serde_json::to_string_pretty(containers).unwrap();
    let mut file = OpenOptions::new()
        .write(true)
        .truncate(true)
        .create(true)
        .open(config_path)
        .unwrap();
    file.write_all(config_data.as_bytes()).unwrap();
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
        .get_matches();

    if let Some(matches) = matches.subcommand_matches("create") {
        let name = matches.get_one::<String>("name").unwrap();
        let image = matches.get_one::<String>("image").unwrap();
        handle_create(name, image);
    }

    // Handle other commands here...
}