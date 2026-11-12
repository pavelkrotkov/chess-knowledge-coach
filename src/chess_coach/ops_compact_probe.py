"""Build the isolated interpreter and installed-RECORD probe."""

import sysconfig
from pathlib import Path


def site_path(venv):
    return Path(sysconfig.get_path("purelib", vars={"base": str(venv), "platbase": str(venv)}))


def script():
    return (
        "import json,sys,sysconfig; from pathlib import Path; "
        "from importlib.metadata import distributions; "
        "site=sysconfig.get_paths()['purelib']; root=Path(sys.prefix).resolve(); "
        "items=list(distributions(path=[site])); "
        "dists=[[d.metadata['Name'],d.version] for d in items]; "
        "records=all(d.files and all((p:=Path(d.locate_file(f)).resolve()).is_relative_to(root) "
        "and p.is_file() for f in d.files) for d in items); "
        "print(json.dumps([list(sys.version_info[:3]),sys.implementation.cache_tag,"
        "sys.base_prefix,sys.prefix,site,dists,records]))"
    )
