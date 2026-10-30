"""Run the seven inherited export audits only after current-lock suites complete."""
import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def main():
    lh=sha(ROOT/"runtime-lock.json");lock=load(ROOT/"runtime-lock.json")
    entries=[("association-plan-acceptance-*","audit_association_plan_exports.py"),("survival-acceptance-*","audit_survival_exports.py"),("survival-v05-acceptance-*","audit_survival_v05_exports.py"),("survival-v06-acceptance-*","audit_survival_v06_exports.py"),("psm-v07-acceptance-*","audit_psm_v07_exports.py"),("penalized-v08-acceptance-*","audit_penalized_v08_exports.py"),("interpretation-v09-acceptance-*","audit_interpretation_v09_exports.py")]
    selected=[]
    for pattern,tool in entries:
        candidates=[p for p in sorted((ROOT/"evidence").glob(pattern+"/acceptance-receipt.json")) if load(p).get("runtime_lock_sha256")==lh]
        assert candidates,pattern
        receipt=candidates[-1];value=load(receipt);assert value["summary"]["failed"]==0
        selected.append((receipt,tool))
    out=ROOT/"evidence"/("export-audits-v10-"+time.strftime("%Y%m%d-%H%M%S"));out.mkdir(exist_ok=False)
    rows=[]
    for receipt,tool in selected:
        target=receipt.parent/"export-audit.json";assert not target.exists(),"Existing audit retained: "+str(target)
        proc=subprocess.run([lock["python"],"-B","-X","utf8",str(ROOT/"tools"/tool),str(receipt.parent)],cwd=ROOT,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},capture_output=True,timeout=120)
        log=out/(tool+".log");log.write_bytes(proc.stdout+b"\n"+proc.stderr)
        value=load(target) if target.exists() else {"status":"MISSING"}
        passed=proc.returncode==0 and value["status"]=="PASS" and value.get("runtime_lock_sha256")==lh and value.get("acceptance_receipt_sha256")==sha(receipt) and value.get("audit_script_sha256")==sha(ROOT/"tools"/tool)
        row={"tool":tool,"status":"PASS" if passed else "FAIL","returncode":proc.returncode,"audit":str(target.relative_to(ROOT)),"log":str(log.relative_to(ROOT)),"log_sha256":sha(log)};rows.append(row);print(json.dumps(row),flush=True)
    stable=sha(ROOT/"runtime-lock.json")==lh and all(sha(ROOT/p)==h for p,h in lock["code_hashes"].items())
    result={"status":"PASS" if stable and all(x["status"]=="PASS" for x in rows) else "FAIL","runtime_lock_sha256":lh,"production_unchanged":stable,"runs":rows}
    (out/"runner-receipt.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"receipt":str(out/"runner-receipt.json")}),flush=True)
    return int(result["status"]!="PASS")
if __name__=="__main__":raise SystemExit(main())
