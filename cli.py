#!/usr/bin/env python3
"""stegtool command line interface (thin layer over the ``stego`` package)."""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from stego import analysis
from stego.image_lsb import decode_image, encode_image
from stego.text_zw import STRIP_WARNING, decode_text, encode_text
from stego.utils import (
    Extracted,
    StegoError,
    format_size,
    read_file,
    safe_filename,
    write_file,
)

DISCLAIMER = (
    "Steganography HIDES data; encryption (--password) PROTECTS it. "
    "Use responsibly: privacy, learning, watermarking, CTFs."
)


# --------------------------------------------------------------------------- helpers
def _secret(args: argparse.Namespace) -> tuple[bytes, str | None]:
    if args.file:
        path = Path(args.file)
        return read_file(path), path.name
    return args.message.encode("utf-8"), None


def _password(args: argparse.Namespace) -> str | None:
    if args.ask_password:
        return getpass.getpass("Password: ") or None
    return args.password or None


def _say(args: argparse.Namespace, msg: str) -> None:
    """Status messages go to stderr when the real result is printed on stdout."""
    print(msg, file=sys.stderr if getattr(args, "_stdout_result", False) else sys.stdout)


def _deliver(args: argparse.Namespace, res: Extracted) -> None:
    """Print a recovered text secret, or save a recovered file."""
    if not res.is_file:
        if args.output:
            out = write_file(args.output, res.data, overwrite=args.force)
            print(f"[OK] Hidden message saved to {out}")
        else:
            print(res.text())
        return
    target = args.output or f"extracted_{safe_filename(res.filename or '')}"
    out = write_file(target, res.data, overwrite=args.force)
    print(f"[OK] Hidden file '{res.filename}' ({format_size(len(res.data))}) saved to {out}")


def _flags(compress: bool, password: str | None, random_order: bool = False) -> str:
    enc = "AES-256-GCM + Scrypt" if password else "no (hidden but NOT encrypted)"
    parts = [f"Encrypted: {enc}", f"Compressed: {'yes' if compress else 'no'}"]
    if random_order:
        parts.append("Random pixel order: yes")
    return " | ".join(parts)


# --------------------------------------------------------------------------- commands
def cmd_image_encode(args: argparse.Namespace) -> int:
    data, name = _secret(args)
    password = _password(args)
    output = args.output or str(Path(args.input).with_name(Path(args.input).stem + "_stego.png"))
    r = encode_image(args.input, output, data, filename=name, password=password,
                     compress=not args.no_compress, random_order=args.random, overwrite=args.force)
    print(f"[OK] Secret hidden in {r.output_path}")
    print(f"     Capacity : {format_size(r.payload_bytes)} of {format_size(r.capacity_bytes)} used ({r.used_percent:.2f}%)")
    print(f"     Options  : {_flags(not args.no_compress, password, args.random)}")
    psnr = "inf (identical)" if r.psnr == float("inf") else f"{r.psnr:.2f} dB"
    print(f"     Quality  : MSE {r.mse:.5f} | PSNR {psnr}")
    print("     Keep the output as PNG/BMP - JPEG or social-media re-compression destroys it.")
    return 0


def cmd_image_decode(args: argparse.Namespace) -> int:
    _deliver(args, decode_image(args.input, password=_password(args)))
    return 0


def cmd_image_analyze(args: argparse.Namespace) -> int:
    r = analysis.analyze_image(args.input)
    print(f"Chi-square LSB test for {args.input}")
    print(f"     chi2 = {r.chi2:.1f}  (dof {r.dof})  p = {r.p_value:.4f}  [strongest at first {r.window_fraction:.0%} of pixels]")
    print(f"     Suspicion: {r.level.upper()} - {r.summary}")
    print("     Heuristic only: it cannot prove presence/absence, esp. for short or random-order messages.")
    return 0


def cmd_text_encode(args: argparse.Namespace) -> int:
    cover = args.cover_text if args.cover_text is not None else read_file(args.cover).decode("utf-8")
    data, name = _secret(args)
    password = _password(args)
    args._stdout_result = not args.output
    r = encode_text(cover, data, filename=name, password=password,
                    compress=not args.no_compress, spread=not args.no_spread)
    if args.output:
        write_file(args.output, r.text.encode("utf-8"), overwrite=args.force)
    else:
        print(r.text)
    _say(args, f"[OK] Hidden {r.hidden_chars} invisible characters in {r.visible_chars} visible ones "
               f"({r.density:.1f} per char){' -> ' + args.output if args.output else ''}")
    _say(args, f"     Capacity : {format_size(r.payload_bytes)} of {format_size(r.capacity_bytes)} ({100 * r.payload_bytes / max(1, r.capacity_bytes):.1f}%)")
    _say(args, f"     Options  : {_flags(not args.no_compress, password)}")
    _say(args, f"[!]  {STRIP_WARNING}")
    return 0


def cmd_text_decode(args: argparse.Namespace) -> int:
    text = read_file(args.input).decode("utf-8") if args.input else sys.stdin.read()
    _deliver(args, decode_text(text, password=_password(args)))
    return 0


# --------------------------------------------------------------------------- parser
def _add_secret(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("-m", "--message", help="secret text to hide")
    g.add_argument("-f", "--file", help="secret file to hide")
    p.add_argument("--no-compress", action="store_true", help="skip zlib compression")


def _add_password(p: argparse.ArgumentParser) -> None:
    p.add_argument("-p", "--password", help="encrypt/decrypt with this password (visible in shell history!)")
    p.add_argument("--ask-password", action="store_true", help="prompt for the password instead")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stegtool", description="Image + text steganography tool.", epilog=DISCLAIMER)
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("image-encode", help="hide a message/file in a PNG/BMP", epilog=DISCLAIMER)
    p.add_argument("-i", "--input", required=True, help="cover image (PNG/BMP)")
    p.add_argument("-o", "--output", help="stego image to create (default: <input>_stego.png)")
    _add_secret(p); _add_password(p)
    p.add_argument("--random", action="store_true", help="random pixel order seeded from the password")
    p.add_argument("--force", action="store_true", help="overwrite the output if it exists")
    p.set_defaults(func=cmd_image_encode)

    p = sub.add_parser("image-decode", help="extract hidden data from a stego image")
    p.add_argument("-i", "--input", required=True, help="stego image")
    p.add_argument("-o", "--output", help="where to save the result (needed to save text; files default to extracted_<name>)")
    _add_password(p)
    p.add_argument("--force", action="store_true", help="overwrite the output if it exists")
    p.set_defaults(func=cmd_image_decode)

    p = sub.add_parser("image-analyze", help="chi-square LSB test")
    p.add_argument("-i", "--input", required=True, help="image to analyse (PNG/BMP)")
    p.set_defaults(func=cmd_image_analyze)

    p = sub.add_parser("text-encode", help="hide a message/file in cover text (zero-width chars)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("-c", "--cover", help="cover text file (UTF-8)")
    g.add_argument("--cover-text", help="cover text given inline")
    p.add_argument("-o", "--output", help="write stego text here (default: print to stdout)")
    _add_secret(p); _add_password(p)
    p.add_argument("--no-spread", action="store_true", help="put all hidden characters in one spot")
    p.add_argument("--force", action="store_true", help="overwrite the output if it exists")
    p.set_defaults(func=cmd_text_encode)

    p = sub.add_parser("text-decode", help="extract hidden data from stego text")
    p.add_argument("-i", "--input", help="stego text file (default: read stdin)")
    p.add_argument("-o", "--output", help="save the result to a file")
    _add_password(p)
    p.add_argument("--force", action="store_true", help="overwrite the output if it exists")
    p.set_defaults(func=cmd_text_decode)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # zero-width text must survive Windows consoles
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except StegoError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
