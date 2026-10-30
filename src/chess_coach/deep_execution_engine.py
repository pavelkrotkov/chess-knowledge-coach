"""Start a reproducible engine outside database transactions."""

from contextlib import suppress
from types import SimpleNamespace

import chess.engine


def start_engine(binary, config, *, timeout=5.0):
    try:
        engine = chess.engine.SimpleEngine.popen_uci(str(binary), timeout=timeout)
        settings = {"Threads": config["threads"], "Hash": config["hash_mb"]}
        config["native_wdl_requested"] = "UCI_ShowWDL" in engine.options
        if config["native_wdl_requested"]:
            settings["UCI_ShowWDL"] = True
        engine.configure(settings)
        metadata = SimpleNamespace(id=dict(engine.id), options=dict(engine.options))
        config["engine_id"] = dict(metadata.id)
        config["nnue_options"] = {
            name: str(option.default)
            for name, option in metadata.options.items()
            if "nnue" in name.lower() or "evalfile" in name.lower()
        }
        return engine, metadata
    except Exception:
        if "engine" in locals():
            with suppress(Exception):
                engine.close()
        raise RuntimeError("deep engine could not be started") from None


def stop_engine(engine):
    try:
        engine.quit()
        return True
    except Exception:
        with suppress(Exception):
            engine.close()
        return False
