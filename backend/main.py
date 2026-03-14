"""Entry: load config, init logging, run migrations, bootstrap admin, start job runner thread, start server."""

import sys
import logging
import threading

from backend.config import load_config
from backend.logging_config import configure_logging
from backend.storage.sqlite import run_migrations
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.app import app
from backend.jobs.runner import run_loop
import uvicorn

logger = logging.getLogger(__name__)

_runner_stop = threading.Event()
_runner_thread: threading.Thread | None = None


def main() -> None:
    global _runner_thread
    config = load_config()
    app.state.config = config
    configure_logging(config.log_level)
    run_migrations(config.database_path)
    password = ensure_bootstrap_admin(config.database_path)
    if password is not None:
        print("Bootstrap admin password (save it; shown once):", password, file=sys.stderr)
    _runner_stop.clear()
    _runner_thread = threading.Thread(target=run_loop, args=(config,), kwargs={"stop_event": _runner_stop, "interval_seconds": 2.0}, daemon=True)
    _runner_thread.start()
    logger.info("Starting server")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
