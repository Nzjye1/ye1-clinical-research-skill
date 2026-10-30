"""Bounded parallel official-wheel acquisition with a product-local resume cache."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib,json,time,urllib.parse,urllib.request
from runtime_windows import need,sha,RuntimeErrorCode

def acquire(spec,directory,log_path):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);log_path=Path(log_path)
    need(not directory.is_symlink(),"UNSAFE_WHEEL_DIRECTORY")
    def one(record):
        name=record["filename"];url=urllib.parse.urlparse(record["url"])
        need(Path(name).name==name and name.endswith(".whl") and url.scheme=="https" and url.hostname=="files.pythonhosted.org","OFFICIAL_WHEEL_SOURCE_REQUIRED")
        target=directory/name;need(not target.is_symlink(),"UNSAFE_WHEEL_PATH")
        if target.is_file() and sha(target)==record["sha256"]:return {"package":record["name"],"status":"reused_verified_wheel","bytes":target.stat().st_size}
        partial=directory/(name+".part");need(not partial.is_symlink(),"UNSAFE_WHEEL_PATH")
        digest=hashlib.sha256();count=0;started=time.monotonic()
        with urllib.request.urlopen(record["url"],timeout=30) as response,partial.open("wb") as output:
            length=int(response.headers.get("Content-Length","0"));need(0<=length<=150_000_000,"WHEEL_DOWNLOAD_SIZE_UNSUPPORTED")
            while True:
                need(time.monotonic()-started<=3600,"WHEEL_DOWNLOAD_TIME_LIMIT")
                block=response.read(262144)
                if not block:break
                count+=len(block);need(count<=150_000_000,"WHEEL_DOWNLOAD_SIZE_UNSUPPORTED");output.write(block);digest.update(block)
        need(digest.hexdigest()==record["sha256"],"PYTHON_WHEEL_HASH_MISMATCH")
        partial.replace(target)
        return {"package":record["name"],"status":"downloaded_and_verified","bytes":count}
    successes=[];failures=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(one,x):x["name"] for x in spec["python_packages"]}
        for future in as_completed(pending):
            name=pending[future]
            try:
                item=future.result();successes.append(item)
                print(json.dumps({"stage":"verified_wheel","package":name,"completed":len(successes),"total":len(spec["python_packages"]),"cache":"product_local"}),flush=True)
            except Exception as error:
                failures.append({"package":name,"reason_code":getattr(error,"code","NETWORK_OR_LOCAL_DOWNLOAD_FAILED")})
    log_path.write_text(json.dumps({"official_sources":"runtime-spec.json","successes":successes,"failures":failures,"cache":str(directory)},indent=2),encoding="utf-8")
    if failures:raise RuntimeErrorCode("PYTHON_WHEEL_DOWNLOAD_FAILED")
    return directory
