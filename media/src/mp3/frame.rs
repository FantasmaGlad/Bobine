use super::*;

#[derive(Clone, Copy, PartialEq, Debug)]
pub(super) struct Frame {
    pub(super) mpeg1: bool,
    pub(super) mono: bool,
    pub(super) bitrate: u64,
    pub(super) rate: u64,
    pub(super) samples: u64,
    pub(super) length: u64,
    pub(super) protected: bool,
    pub(super) version_bits: u8,
    pub(super) bitrate_index: u8,
    pub(super) rate_index: u8,
}

pub(super) const BITRATES_MPEG1: [u64; 15] = [
    0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320,
];

pub(super) const BITRATES_MPEG2: [u64; 15] =
    [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160];

pub(super) fn parse_frame(header: [u8; 4]) -> Option<Frame> {
    if header[0] != 0xff || header[1] & 0xe0 != 0xe0 || header[1] & 6 != 2 {
        return None;
    }
    let version_bits = (header[1] >> 3) & 3;
    let mpeg1 = match version_bits {
        3 => true,
        0 | 2 => false,
        _ => return None,
    };
    let bitrate_index = header[2] >> 4;
    let rate_index = (header[2] >> 2) & 3;
    if bitrate_index == 0 || bitrate_index == 15 || rate_index == 3 {
        return None;
    }
    let rate = match (version_bits, rate_index) {
        (3, 0) => 44_100,
        (3, 1) => 48_000,
        (3, 2) => 32_000,
        (2, 0) => 22_050,
        (2, 1) => 24_000,
        (2, 2) => 16_000,
        (0, 0) => 11_025,
        (0, 1) => 12_000,
        _ => 8_000,
    };
    let bitrate = 1000
        * if mpeg1 {
            BITRATES_MPEG1[usize::from(bitrate_index)]
        } else {
            BITRATES_MPEG2[usize::from(bitrate_index)]
        };
    let padding = u64::from((header[2] >> 1) & 1);
    let length = if mpeg1 { 144 } else { 72 } * bitrate / rate + padding;
    Some(Frame {
        mpeg1,
        mono: header[3] >> 6 == 3,
        bitrate,
        rate,
        samples: if mpeg1 { 1152 } else { 576 },
        length,
        protected: header[1] & 1 == 0,
        version_bits,
        bitrate_index,
        rate_index,
    })
}

impl Frame {
    pub(super) fn same_stream(&self, other: &Frame) -> bool {
        self.version_bits == other.version_bits
            && self.bitrate_index == other.bitrate_index
            && self.rate_index == other.rate_index
            && self.mono == other.mono
    }
}

#[derive(Default)]
struct Chain {
    frames: u64,
    position: u64,
    header: [u8; 4],
    have: usize,
    skip: u64,
}

impl Chain {
    fn feed(&mut self, bytes: &[u8], total: u64, first: &Frame) -> Result<()> {
        let mut at = 0;
        while at < bytes.len() {
            if self.skip > 0 {
                let take = (self.skip as usize).min(bytes.len() - at);
                self.skip -= take as u64;
                at += take;
                self.position += take as u64;
                continue;
            }
            if self.position == total {
                return Err(unsupported());
            }
            self.header[self.have] = bytes[at];
            self.have += 1;
            at += 1;
            self.position += 1;
            if self.have == 4 {
                self.complete_header(total, first)?;
            }
        }
        Ok(())
    }

    fn complete_header(&mut self, total: u64, first: &Frame) -> Result<()> {
        let frame = parse_frame(self.header).ok_or_else(unsupported)?;
        if !frame.same_stream(first) {
            return Err(unsupported());
        }
        self.skip = frame.length - 4;
        self.frames += 1;
        self.have = 0;
        if self.position + self.skip > total {
            return Err(unsupported());
        }
        Ok(())
    }
}

pub(super) fn chain<R: Read>(reader: &mut R, total: u64, first: &Frame) -> Result<u64> {
    let mut state = Chain::default();
    let mut buffer = vec![0_u8; 64 * 1024];
    loop {
        if state.position == total && state.have == 0 && state.skip == 0 {
            return Ok(state.frames);
        }
        let count = reader.read(&mut buffer).map_err(|error| {
            if error.kind() == std::io::ErrorKind::Other {
                limit()
            } else {
                corrupt()
            }
        })?;
        if count == 0 {
            return Err(corrupt());
        }
        state.feed(&buffer[..count], total, first)?;
    }
}

pub(super) fn vbri_duration<R: Read>(
    reader: &mut R,
    samples_per_frame: u64,
    sample_rate: u64,
) -> Result<f64> {
    let mut fields = [0; 14];
    read_exact(reader, &mut fields)?;
    let version = u16::from_be_bytes([fields[0], fields[1]]);
    let frames = u64::from(u32::from_be_bytes([
        fields[10], fields[11], fields[12], fields[13],
    ]));
    if version != 1 || frames == 0 {
        return Err(unsupported());
    }
    Ok((frames * samples_per_frame) as f64 / sample_rate as f64)
}

pub(super) fn xing_duration<R: Read>(
    reader: &mut R,
    samples_per_frame: u64,
    sample_rate: u64,
) -> Result<f64> {
    let mut word = [0; 4];
    read_exact(reader, &mut word)?;
    let flags = u32::from_be_bytes(word);
    if flags & 1 == 0 {
        return Err(unsupported());
    }
    read_exact(reader, &mut word)?;
    let frames = u64::from(u32::from_be_bytes(word));
    if frames == 0 {
        return Err(unsupported());
    }
    let mut skip = [0; 100];
    if flags & 2 != 0 {
        read_exact(reader, &mut word)?;
    }
    if flags & 4 != 0 {
        read_exact(reader, &mut skip)?;
    }
    if flags & 8 != 0 {
        read_exact(reader, &mut word)?;
    }
    let mut lame = [0; 24];
    read_exact(reader, &mut lame)?;
    let total = frames.checked_mul(samples_per_frame).ok_or_else(corrupt)?;
    let samples = if matches!(&lame[..4], b"LAME" | b"Lavf" | b"Lavc") {
        let delays = u32::from_be_bytes([0, lame[21], lame[22], lame[23]]);
        let trim = u64::from(delays >> 12) + u64::from(delays & 0xfff);
        if trim >= total {
            return Err(corrupt());
        }
        total - trim
    } else {
        total
    };
    Ok(samples as f64 / sample_rate as f64)
}
