from __future__ import annotations

import argparse
import io
import ipaddress
import json
import sys
import uuid
from collections.abc import Sequence

from .csv_logger import AndroidCSVLogger
from .http_server import ProbeHTTPServer, ProbeIPv6HTTPServer, ProbeRequestHandler
from .security import generate_token, redact_token
from .state import ReceiverSession


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Receive Android wifiops probe telemetry.")
    parser.add_argument("--pair", action="store_true", required=True, help="Create a QR/manual pairing session")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host. Use 0.0.0.0, ::, or an interface IP for phone access.",
    )
    parser.add_argument("--port", type=int, default=8765, help="Bind port")
    parser.add_argument("--advertise-host", default="", help="Host/IP encoded into the pairing URL")
    parser.add_argument("--log", help="Optional Android telemetry CSV log path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(sys.argv[1:] if argv is None else argv))

    token = generate_token()
    session = ReceiverSession(session_id=f"walk_{uuid.uuid4().hex[:12]}", token=token)
    logger = AndroidCSVLogger(args.log) if args.log else None
    advertised_host = args.advertise_host or args.host
    receiver_url = receiver_url_for_host(advertised_host, args.port)
    pairing_payload = build_pairing_payload(receiver_url, session.session_id, token)

    if not is_loopback_host(args.host):
        print(f"Warning: receiver is exposed on {format_host_port(args.host, args.port)}. Use only on trusted LANs.")
    print(f"Receiver URL: {receiver_url}")
    print(f"Session ID: {session.session_id}")
    print(f"Token: {redact_token(token)}")
    print(render_pairing_qr(pairing_payload))
    print("Pairing payload:")
    print(json.dumps(pairing_payload, sort_keys=True))

    server_class = ProbeIPv6HTTPServer if is_ipv6_literal(args.host) else ProbeHTTPServer
    server = server_class(
        (args.host, args.port),
        ProbeRequestHandler,
        session=session,
        csv_logger=logger,
        on_probe_connected=lambda record: print(
            f"Probe connected: device={record.device_id} session={record.session_id} first_record={record.record_id}",
            flush=True,
        ),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        if logger:
            logger.close()
    return 0


def build_pairing_payload(receiver_url: str, session_id: str, token: str) -> dict[str, str]:
    return {
        "receiver_url": receiver_url,
        "session_id": session_id,
        "token": token,
    }


def render_pairing_qr(pairing_payload: dict[str, str]) -> str:
    payload_json = json.dumps(pairing_payload, sort_keys=True)
    try:
        import qrcode
    except ImportError:
        return "Scan receiver QR code: unavailable. Install the qrcode package or paste the setup JSON below."

    qr = qrcode.QRCode(border=1)
    qr.add_data(payload_json)
    qr.make(fit=True)
    output = io.StringIO()
    qr.print_ascii(out=output, tty=False)
    return f"Scan receiver QR code:\n{output.getvalue().rstrip()}"


def receiver_url_for_host(host: str, port: int) -> str:
    return f"http://{format_host_port(host, port)}"


def format_host_port(host: str, port: int) -> str:
    if is_ipv6_literal(host):
        return f"[{host}]:{port}"
    return f"{host}:{port}"


def is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def is_ipv6_literal(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).version == 6
    except ValueError:
        return False
