from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections.abc import Sequence

from .csv_logger import AndroidCSVLogger
from .http_server import ProbeHTTPServer, ProbeRequestHandler
from .security import generate_token, redact_token
from .state import ReceiverSession


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Receive Android wifiops probe telemetry.")
    parser.add_argument("--pair", action="store_true", required=True, help="Create a QR/manual pairing session")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host. Use 0.0.0.0 or an interface IP for phone access.",
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
    receiver_url = f"http://{advertised_host}:{args.port}"
    pairing_payload = {
        "receiver_url": receiver_url,
        "session_id": session.session_id,
        "token": token,
    }

    if args.host not in ("127.0.0.1", "localhost"):
        print(f"Warning: receiver is exposed on {args.host}:{args.port}. Use only on trusted LANs.")
    print(f"Receiver URL: {receiver_url}")
    print(f"Session ID: {session.session_id}")
    print(f"Token: {redact_token(token)}")
    print("Pairing payload:")
    print(json.dumps(pairing_payload, sort_keys=True))

    server = ProbeHTTPServer((args.host, args.port), ProbeRequestHandler, session=session, csv_logger=logger)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
        if logger:
            logger.close()
    return 0
