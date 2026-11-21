"""Run the bounded native codec with nonblocking, backpressured pipes."""

import os
import selectors
import subprocess

from .recovery_zstd_pump import pump

MEMORY_BYTES = 48 * 1024 * 1024
PREFIX = ("/usr/bin/prlimit", f"--as={MEMORY_BYTES}", "--", "/usr/bin/zstd")


def transform(source, target, arguments, input_bytes, output_limit, guard, deadline, *, restoring):
    process = subprocess.Popen(
        [*PREFIX, *arguments],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
        env={"LC_ALL": "C"},
    )
    try:
        assert process.stdin is not None and process.stdout is not None
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdin, selectors.EVENT_WRITE, "input")
            selector.register(process.stdout, selectors.EVENT_READ, "output")
            result = pump(
                selector,
                source,
                target,
                input_bytes,
                output_limit,
                guard,
                deadline,
                restoring,
            )
        if process.wait(timeout=1) != 0:
            raise ValueError("Zstandard codec failed")
        return result
    except BrokenPipeError:
        raise ValueError("Zstandard codec failed") from None
    finally:
        for pipe in (process.stdin, process.stdout):
            if pipe is not None:
                pipe.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        else:
            process.wait()
