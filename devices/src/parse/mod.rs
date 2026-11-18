pub mod macos;
pub mod windows;

#[cfg(test)]
mod tests;

pub fn dbm_to_percent(dbm: f64) -> u8 {
    (2.0 * (dbm + 100.0)).clamp(0.0, 100.0).round() as u8
}

pub fn subnet_cidr(ip: &str, mask: &str) -> Option<String> {
    let ip: Vec<u8> = ip
        .split('.')
        .map(|p| p.parse().ok())
        .collect::<Option<Vec<u8>>>()?;
    if ip.len() != 4 {
        return None;
    }
    let mask_bits: u32 = if let Some(hex) = mask.strip_prefix("0x") {
        u32::from_str_radix(hex, 16).ok()?
    } else {
        let parts: Vec<u8> = mask
            .split('.')
            .map(|p| p.parse().ok())
            .collect::<Option<Vec<u8>>>()?;
        if parts.len() != 4 {
            return None;
        }
        u32::from_be_bytes([parts[0], parts[1], parts[2], parts[3]])
    };
    let prefix = mask_bits.count_ones();
    if mask_bits.leading_ones() != prefix {
        return None; // non-contiguous mask
    }
    let ip_bits = u32::from_be_bytes([ip[0], ip[1], ip[2], ip[3]]);
    let net = ip_bits & mask_bits;
    let b = net.to_be_bytes();
    Some(format!("{}.{}.{}.{}/{}", b[0], b[1], b[2], b[3], prefix))
}
