#![no_main]

use bobine_media::fuzzing::{scan, Format};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    scan(Format::Mp3, data, false);
    scan(Format::Mp3, data, true);
});
