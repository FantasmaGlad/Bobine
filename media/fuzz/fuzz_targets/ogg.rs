#![no_main]

use bobine_media::fuzzing::{scan, Format};
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    scan(Format::Ogg, data, false);
    scan(Format::Ogg, data, true);
});
