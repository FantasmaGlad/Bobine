mod exec;
mod parse;
mod platform;
mod protocol;
#[cfg_attr(not(windows), allow(dead_code))]
mod secret_file;

use std::io::{BufRead, Read, Write};

#[derive(Debug, PartialEq)]
enum Line {
    End,
    TooLong,
    Text(String),
}

fn read_bounded_line<R: BufRead>(reader: &mut R, max: usize) -> Line {
    let mut bytes = Vec::new();
    match reader
        .by_ref()
        .take(max as u64 + 1)
        .read_until(b'\n', &mut bytes)
    {
        Ok(0) | Err(_) => return Line::End,
        Ok(_) => {}
    }
    if bytes.len() > max {
        if !bytes.ends_with(b"\n") && reader.skip_until(b'\n').is_err() {
            return Line::End;
        }
        return Line::TooLong;
    }
    match String::from_utf8(bytes) {
        Ok(text) => Line::Text(text),
        Err(_) => Line::End,
    }
}

fn main() {
    let platform = platform::current();
    let stdin = std::io::stdin();
    let stdout = std::io::stdout();
    let mut out = stdout.lock();
    let mut reader = stdin.lock();
    loop {
        let line = match read_bounded_line(&mut reader, protocol::MAX_LINE_BYTES) {
            Line::End => break,
            Line::TooLong => {
                let reply = r#"{"jsonrpc":"2.0","id":null,"error":{"code":-32600,"message":"Requête trop longue"}}"#;
                let _ = writeln!(out, "{reply}");
                let _ = out.flush();
                continue;
            }
            Line::Text(text) => text,
        };
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let reply = protocol::handle_line(platform.as_ref(), trimmed);
        if writeln!(out, "{reply}").is_err() || out.flush().is_err() {
            break;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::{BufReader, Cursor};

    #[test]
    fn long_line_is_refused_without_buffering_it() {
        let mut input = vec![b'x'; 1024 * 1024];
        input.extend_from_slice(b"\n{\"ok\":1}\n");
        let mut reader = BufReader::with_capacity(64, Cursor::new(input));
        assert_eq!(read_bounded_line(&mut reader, 16), Line::TooLong);
        assert_eq!(
            read_bounded_line(&mut reader, 16),
            Line::Text("{\"ok\":1}\n".into())
        );
        assert_eq!(read_bounded_line(&mut reader, 16), Line::End);
    }

    #[test]
    fn line_at_the_limit_is_kept() {
        let mut reader = Cursor::new(b"0123456789abcde\n".to_vec());
        assert_eq!(
            read_bounded_line(&mut reader, 16),
            Line::Text("0123456789abcde\n".into())
        );
    }

    #[test]
    fn invalid_utf8_ends_the_channel_as_before() {
        let mut reader = Cursor::new(vec![0xff, b'\n']);
        assert_eq!(read_bounded_line(&mut reader, 16), Line::End);
    }
}
