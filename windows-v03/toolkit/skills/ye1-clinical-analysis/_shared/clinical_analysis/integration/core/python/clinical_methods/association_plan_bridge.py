"""Private numerical transport for association.analyze_plan; no task engine."""
from __future__ import annotations
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import sys
sys.dont_write_bytecode = True
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_ROWS = 200
if __package__:
    from . import bridge as transport
else:
    import bridge as transport


def canonical_bytes(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")


def provider_version():
    root=Path(__file__).parent
    return hashlib.sha256(canonical_bytes({name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in ("association.py","association_plan_bridge.py","bridge.py","resource_budget.py")})).hexdigest()


def _finite_tree(value):
    if isinstance(value,float):return math.isfinite(value)
    if isinstance(value,dict):return all(isinstance(k,str) and _finite_tree(v) for k,v in value.items())
    if isinstance(value,(list,tuple)):return all(_finite_tree(v) for v in value)
    return value is None or isinstance(value,(str,int,bool))


def _load():
    import numpy,scipy,statsmodels
    if __package__:
        from . import association
    else:
        import association
    return association,{"python":platform.python_version(),"numpy":numpy.__version__,"scipy":scipy.__version__,"statsmodels":statsmodels.__version__}


def preflight():
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            _,runtime=_load()
        return {"ok":True,"runtime":runtime,"provider_version":provider_version()}
    except ImportError:return {"ok":False,"reason_code":"PROVIDER_DEPENDENCY_UNAVAILABLE"}
    except Exception:return {"ok":False,"reason_code":"PROVIDER_EXECUTION_FAILED"}


def invoke(request):
    if not (isinstance(request,dict) and set(request) in ({"rows","plan"},{"rows","plan","limits"}) and isinstance(request["rows"],list)
            and 0<len(request["rows"]) and all(isinstance(r,dict) for r in request["rows"])
            and isinstance(request["plan"],dict) and _finite_tree(request)):
        return {"ok":False,"reason_code":"PROVIDER_REQUEST_INVALID"}
    reason=transport.resource_check(request,"association.linear.plan",MAX_ROWS,"association_plan")
    if reason:return {"ok":False,"reason_code":reason}
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            association,runtime=_load()
            record=association.analyze_plan(request["rows"],request["plan"])
        if not _finite_tree(record):return {"ok":False,"reason_code":"PROVIDER_NONFINITE_RESULT"}
        return {"ok":True,"record":record,"runtime":runtime,"provider_version":provider_version(),
                "request_sha256":hashlib.sha256(canonical_bytes(request)).hexdigest()}
    except ImportError:return {"ok":False,"reason_code":"PROVIDER_DEPENDENCY_UNAVAILABLE"}
    except Exception:return {"ok":False,"reason_code":"PROVIDER_EXECUTION_FAILED"}


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    try:byte_limit=transport.cli_byte_limit(args)
    except (ValueError,TypeError,OverflowError):
        print("PROVIDER_ARGUMENTS_INVALID");return 2
    if args[0]=="--preflight":response=preflight()
    else:
        try:
            path=Path(args[0])
            if path.stat().st_size>byte_limit:response={"ok":False,"reason_code":"PROVIDER_INPUT_LIMIT"}
            else:
                def reject_constant(_):raise ValueError("invalid numeric literal")
                response=invoke(json.loads(path.read_text(encoding="utf-8-sig"),parse_constant=reject_constant))
        except Exception:response={"ok":False,"reason_code":"PROVIDER_INPUT_UNREADABLE"}
    try:
        with Path(args[1]).open("x",encoding="utf-8",newline="\n") as stream:
            stream.write(canonical_bytes(response).decode("utf-8")+"\n")
    except Exception:
        print("PROVIDER_OUTPUT_UNAVAILABLE");return 3
    print("PROVIDER_RESPONSE_READY");return 0


if __name__=="__main__":raise SystemExit(main())
