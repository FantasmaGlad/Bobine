use super::*;

pub(super) enum Codec {
    Vorbis { rate: u64, short: u64, long: u64 },
    Opus,
}

pub(super) fn identify(packet: &[u8]) -> Result<Codec> {
    if packet.starts_with(b"\x01vorbis") {
        if packet.len() != 30 || packet[29] != 1 {
            return Err(unsupported());
        }
        let version = u32::from_le_bytes(packet[7..11].try_into().map_err(|_| corrupt())?);
        let rate = u64::from(u32::from_le_bytes(
            packet[12..16].try_into().map_err(|_| corrupt())?,
        ));
        let (short, long) = (packet[28] & 0x0f, packet[28] >> 4);
        if version != 0
            || packet[11] == 0
            || rate == 0
            || !(6..=13).contains(&short)
            || !(6..=13).contains(&long)
            || short > long
        {
            return Err(unsupported());
        }
        return Ok(Codec::Vorbis {
            rate,
            short: 1 << short,
            long: 1 << long,
        });
    }
    if packet.starts_with(b"OpusHead") {
        if packet.len() != 19 || packet[8] != 1 || !(1..=2).contains(&packet[9]) || packet[18] != 0
        {
            return Err(unsupported());
        }
        return Ok(Codec::Opus);
    }
    Err(unsupported())
}

pub(super) fn modes(setup: &[u8]) -> Result<Vec<bool>> {
    if !setup.starts_with(b"\x05vorbis") {
        return Err(unsupported());
    }
    let bit = |index: usize| (setup[index / 8] >> (index % 8)) & 1;
    let value = |start: usize, width: usize| {
        (0..width).fold(0_usize, |acc, offset| {
            acc | usize::from(bit(start + offset)) << offset
        })
    };
    let last = setup
        .iter()
        .rposition(|byte| *byte != 0)
        .ok_or_else(unsupported)?;
    let framing = last * 8 + (7 - setup[last].leading_zeros() as usize);
    let mut found = None;
    for count in 1..=64_usize {
        let Some(start) = framing.checked_sub(41 * count) else {
            break;
        };
        if start < 7 * 8 + 6 {
            break;
        }
        let zero_fields = (0..count).all(|mode| {
            value(start + 41 * mode + 1, 16) == 0 && value(start + 41 * mode + 17, 16) == 0
        });
        if zero_fields && value(start - 6, 6) == count - 1 {
            found = Some((start, count));
        }
    }
    let (start, count) = found.ok_or_else(unsupported)?;
    Ok((0..count).map(|mode| bit(start + 41 * mode) == 1).collect())
}

pub(super) fn vorbis_total(
    packets: &[Vec<u8>],
    modes: &[bool],
    short: u64,
    long: u64,
) -> Result<u64> {
    let mode_bits = usize::BITS - (modes.len() - 1).leading_zeros();
    let mut total = 0;
    let mut previous = 0;
    for packet in packets {
        let first = *packet.first().ok_or_else(unsupported)?;
        if first & 1 != 0 {
            return Err(unsupported());
        }
        let mode = usize::from(first >> 1) & ((1 << mode_bits) - 1);
        let size = if *modes.get(mode).ok_or_else(unsupported)? {
            long
        } else {
            short
        };
        if previous != 0 {
            total += (previous + size) / 4;
        }
        previous = size;
    }
    Ok(total)
}

pub(super) fn opus_samples(packet: &[u8]) -> Result<u64> {
    let toc = *packet.first().ok_or_else(unsupported)?;
    let config = usize::from(toc >> 3);
    let frame: u64 = match config {
        0..=11 => [480, 960, 1920, 2880][config % 4],
        12..=15 => [480, 960][config % 2],
        _ => [120, 240, 480, 960][config % 4],
    };
    let frames = match toc & 3 {
        0 => 1,
        1 | 2 => 2,
        _ => {
            let count = u64::from(*packet.get(1).ok_or_else(corrupt)? & 0x3f);
            if count == 0 {
                return Err(corrupt());
            }
            count
        }
    };
    if frame * frames > 5760 {
        return Err(corrupt());
    }
    Ok(frame * frames)
}
