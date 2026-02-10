"""Run the back office: python -m brightshop [--port 5590]"""
import argparse

from .web.app import create_app


def main():
    parser = argparse.ArgumentParser(prog="brightshop")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5590)
    parser.add_argument("--today", default=None, help="fixed date, default from config")
    args = parser.parse_args()
    app = create_app(today=args.today)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
