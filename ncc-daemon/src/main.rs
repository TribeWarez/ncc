use std::io::{self, BufRead, Write};
use std::sync::{Arc, Mutex};

use ncc_daemon::{default_data_dir, resolve_master_key, Daemon, EventSink};

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "--help" || a == "-h") {
        eprintln!(
            "ncc-daemon [--data-dir DIR] [--transport mock|nym] [--demo]\n\
             \n\
             Reads line-delimited JSON-RPC on stdin and writes responses on stdout.\n\
             Logs and warnings go to stderr; never mix them into the RPC stream.\n\
             Env: NCC_DATA_DIR, NCC_MASTER_KEY, NCC_TRANSPORT, NCC_DEMO, NCC_NYM_GATEWAY"
        );
        return;
    }

    let mut data_dir = default_data_dir();
    let mut transport = std::env::var("NCC_TRANSPORT").unwrap_or_else(|_| "mock".into());
    let mut demo = std::env::var("NCC_DEMO").ok().as_deref() == Some("1");

    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--data-dir" => {
                index += 1;
                if let Some(value) = args.get(index) {
                    data_dir = value.into();
                }
            }
            "--transport" => {
                index += 1;
                if let Some(value) = args.get(index) {
                    transport = value.clone();
                }
            }
            "--demo" => demo = true,
            other => eprintln!("warning: ignoring unknown argument {other:?}"),
        }
        index += 1;
    }

    eprintln!("ncc-daemon: transport={transport} demo={demo}");
    let key = match resolve_master_key(&data_dir) {
        Ok(key) => key,
        Err(err) => {
            eprintln!("error: {err}");
            std::process::exit(2);
        }
    };

    let stdout = Arc::new(Mutex::new(io::stdout()));
    let sink: EventSink = {
        let stdout = Arc::clone(&stdout);
        Arc::new(move |line: String| {
            if let Ok(mut out) = stdout.lock() {
                let _ = writeln!(out, "{line}");
                let _ = out.flush();
            }
        })
    };

    let mut daemon = match Daemon::new(&data_dir, key, &transport, demo, sink) {
        Ok(daemon) => daemon,
        Err(err) => {
            eprintln!("error: {err}");
            std::process::exit(2);
        }
    };

    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = match line {
            Ok(line) => line,
            Err(err) => {
                eprintln!("stdin error: {err}");
                break;
            }
        };
        if line.trim().is_empty() {
            continue;
        }
        if let Some(response) = daemon.handle_line(&line) {
            let write = stdout.lock().map(|mut out| {
                let ok = writeln!(out, "{response}").is_ok();
                let _ = out.flush();
                ok
            });
            if !matches!(write, Ok(true)) {
                break;
            }
        }
        if daemon.should_exit() {
            break;
        }
    }

    daemon.shutdown();
    if let Ok(mut out) = stdout.lock() {
        let _ = out.flush();
    };
}
