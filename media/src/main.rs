use std::io::{self, BufReader, BufWriter};

fn main() {
    let stdin = io::stdin();
    let stdout = io::stdout();
    if let Err(error) =
        bobine_media::serve(BufReader::new(stdin.lock()), BufWriter::new(stdout.lock()))
    {
        eprintln!("media transport failed: {}", error.kind());
        std::process::exit(1);
    }
}
