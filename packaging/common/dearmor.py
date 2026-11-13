import base64
import sys


def dearmor(text: str) -> bytes:
    lines = text.strip().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("-----BEGIN PGP PUBLIC KEY BLOCK"))
    end = next(i for i, line in enumerate(lines) if line.startswith("-----END PGP PUBLIC KEY BLOCK"))
    body = lines[start + 1:end]
    body = body[body.index("") + 1:] if "" in body else body
    return base64.b64decode("".join(line for line in body if not line.startswith("=")))


if __name__ == "__main__":
    with open(sys.argv[1], encoding="ascii") as source, open(sys.argv[2], "wb") as target:
        target.write(dearmor(source.read()))
