"""Select the existing gzip or explicit Zstandard recovery routines."""


def routines(codec):
    if codec == "gzip":
        from .recovery_gzip_manifest_check import validate
        from .recovery_gzip_restore import restore
        from .recovery_gzip_stream import compress

        return compress, restore, validate
    if codec == "zstd":
        from .recovery_zstd_manifest import validate
        from .recovery_zstd_restore import restore
        from .recovery_zstd_stream import compress

        return compress, restore, validate
    raise ValueError("unsupported recovery codec")
