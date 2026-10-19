//! Exécution de commandes système : jamais de shell, délai d'expiration, entrée standard optionnelle.
//! Les arguments sont passés tels quels (aucune interprétation) ; un mot de passe se transmet par
//! `stdin` chaque fois que l'outil le permet, jamais en argument.

use crate::protocol::RpcError;
use std::io::{Read, Write};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

pub struct Output {
    pub code: i32,
    pub stdout: String,
    pub stderr: String,
}

pub fn run(
    program: &str,
    args: &[&str],
    timeout: Duration,
    stdin: Option<&str>,
) -> Result<Output, RpcError> {
    run_with_env(program, args, timeout, stdin, &[])
}

/// Variante avec variables d'environnement : sert à passer une valeur à PowerShell SANS l'interpoler
/// dans le script (`$env:BOBINE_ARG`), donc sans aucun risque d'injection.
pub fn run_with_env(
    program: &str,
    args: &[&str],
    timeout: Duration,
    stdin: Option<&str>,
    envs: &[(&str, &str)],
) -> Result<Output, RpcError> {
    let mut child = Command::new(program)
        .args(args)
        .envs(envs.iter().copied())
        .stdin(if stdin.is_some() {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| match e.kind() {
            std::io::ErrorKind::NotFound => RpcError::app(
                "tool_missing",
                format!("Outil système introuvable : {program}"),
            ),
            _ => RpcError::app(
                "tool_failed",
                format!("Impossible de lancer {program} : {e}"),
            ),
        })?;

    if let (Some(text), Some(mut pipe)) = (stdin, child.stdin.take()) {
        let _ = pipe.write_all(text.as_bytes());
    }
    let mut stdout = child.stdout.take();
    let mut stderr = child.stderr.take();
    let out_reader = thread::spawn(move || read_all(stdout.as_mut()));
    let err_reader = thread::spawn(move || read_all(stderr.as_mut()));

    let started = Instant::now();
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break status,
            Ok(None) if started.elapsed() >= timeout => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(RpcError::app(
                    "timeout",
                    format!("{program} n'a pas répondu dans le délai imparti."),
                ));
            }
            Ok(None) => thread::sleep(Duration::from_millis(20)),
            Err(e) => return Err(RpcError::app("tool_failed", format!("{program} : {e}"))),
        }
    };
    Ok(Output {
        code: status.code().unwrap_or(-1),
        stdout: out_reader.join().unwrap_or_default(),
        stderr: err_reader.join().unwrap_or_default(),
    })
}

fn read_all<R: Read>(reader: Option<&mut R>) -> String {
    let mut buffer = Vec::new();
    if let Some(r) = reader {
        let _ = r.take(4 * 1024 * 1024).read_to_end(&mut buffer);
    }
    String::from_utf8_lossy(&buffer).into_owned()
}

/// Vrai si l'outil est trouvé dans le PATH.
pub fn tool_exists(program: &str) -> bool {
    let Some(path) = std::env::var_os("PATH") else {
        return false;
    };
    std::env::split_paths(&path).any(|dir| {
        let candidate = dir.join(program);
        candidate.is_file() || candidate.with_extension("exe").is_file()
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn missing_tool_is_a_structured_error() {
        let err = match run(
            "definitely-not-a-real-tool-xyz",
            &[],
            Duration::from_secs(1),
            None,
        ) {
            Err(e) => e,
            Ok(_) => panic!("attendu : erreur"),
        };
        assert_eq!(err.data.unwrap()["code"], "tool_missing");
    }

    #[cfg(unix)]
    #[test]
    fn runs_with_stdin_and_times_out() {
        let out = run("cat", &[], Duration::from_secs(5), Some("bonjour")).unwrap();
        assert_eq!((out.code, out.stdout.as_str()), (0, "bonjour"));
        let err = match run("sleep", &["5"], Duration::from_millis(100), None) {
            Err(e) => e,
            Ok(_) => panic!("attendu : délai dépassé"),
        };
        assert_eq!(err.data.unwrap()["code"], "timeout");
    }
}
