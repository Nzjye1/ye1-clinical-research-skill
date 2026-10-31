"""Fetch the fixed official Apple Silicon installation inputs to a new cache."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
import argparse, hashlib, json, time, urllib.error, urllib.request

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / 'macos' / name).read_text(encoding='utf-8'))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    args.root.mkdir(parents=True, exist_ok=False)
    bootstrap = read('bootstrap-lock.json')['artifacts']
    wheels = read('python-arm64-lock.json')['artifacts']
    r = read('r-arm64-lock.json')
    jobs = [('bootstrap', item, item['sha256'] + '_' + item['filename']) for item in bootstrap]
    jobs += [('wheels', item, item['filename']) for item in wheels]
    jobs += [('r', item, item['filename']) for item in r['binary_packages'] + r['build_dependencies']]

    def fetch(job):
        group, item, filename = job
        url = urlparse(item['url'])
        if url.scheme != 'https' or url.hostname not in {'files.pythonhosted.org', 'cran.r-project.org', 'www.python.org'}:
            raise ValueError('unapproved download host: ' + item['name'])
        if Path(filename).name != filename:
            raise ValueError('unsafe filename')
        directory = args.root / group
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        errors = []
        for attempt in range(1, 4):
            partial = directory / (filename + f'.attempt-{attempt}.part')
            h = hashlib.sha256()
            count = 0
            try:
                with urllib.request.urlopen(item['url'], timeout=120) as response, partial.open('xb') as output:
                    while True:
                        data = response.read(262144)
                        if not data:
                            break
                        count += len(data)
                        if count > 200_000_000:
                            raise ValueError('download exceeds bound')
                        output.write(data)
                        h.update(data)
                if h.hexdigest() != item['sha256'] or count != item['bytes']:
                    raise ValueError(f"archive mismatch: actual bytes={count} sha256={h.hexdigest()}; expected bytes={item['bytes']} sha256={item['sha256']}")
                partial.rename(path)
                return {'group': group, 'name': item['name'], 'file': path.relative_to(args.root).as_posix(),
                        'sha256': item['sha256'], 'bytes': count, 'url': item['url'], 'attempts': attempt,
                        'previous_failures': errors}
            except (OSError, ValueError) as error:
                if isinstance(error, PermissionError) or (isinstance(error, urllib.error.HTTPError) and error.code in (401, 403)):
                    raise
                errors.append(str(error))
                print(json.dumps({'retry': item['name'], 'attempt': attempt, 'error': str(error)}), flush=True)
                if attempt < 3:
                    time.sleep(attempt)
        raise ValueError('official download failed; all partials retained: ' + '; '.join(errors))

    results, failures = [], []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch, job): job[1]['name'] for job in jobs}
        for future in as_completed(futures):
            try:
                record = future.result()
                results.append(record)
                print(json.dumps({'verified': record['name'], 'group': record['group']}), flush=True)
            except Exception as error:
                failures.append({'name': futures[future], 'error': str(error)})
                print(json.dumps({'failed': futures[future], 'error': str(error)}), flush=True)
    (args.root / 'PREFETCH-RECEIPT.json').write_text(json.dumps({'artifacts': sorted(results, key=lambda x:x['file']),
        'failures': failures}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if failures:
        raise SystemExit(1)
    print(json.dumps({'status': 'PASS', 'verified': len(results)}))


if __name__ == '__main__':
    main()
