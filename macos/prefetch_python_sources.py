"""Download matching official PyPI source archives for offline redistribution."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
import argparse, hashlib, json, urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--bootstrap-certifi-only', action='store_true')
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    lock = json.loads((ROOT / 'macos/python-arm64-lock.json').read_text(encoding='utf-8'))
    if args.bootstrap_certifi_only:
        bootstrap = json.loads((ROOT / 'macos/bootstrap-lock.json').read_text(encoding='utf-8'))['artifacts']
        lock['artifacts'] = [next(item for item in bootstrap if item['name'].lower() == 'certifi')]

    def fetch(item):
        metadata_url = f"https://pypi.org/pypi/{item['name']}/{item['version']}/json"
        with urllib.request.urlopen(metadata_url, timeout=60) as response:
            metadata = json.load(response)
        sources = [record for record in metadata['urls'] if record['packagetype'] == 'sdist']
        if len(sources) != 1:
            raise ValueError('official source distribution is missing or ambiguous')
        source = sources[0]
        filename = source['filename']
        url = urlparse(source['url'])
        if Path(filename).name != filename or url.scheme != 'https' or url.hostname != 'files.pythonhosted.org':
            raise ValueError('invalid source filename or host')
        path = args.directory / filename
        partial = args.directory / (filename + '.part')
        h = hashlib.sha256()
        count = 0
        with urllib.request.urlopen(source['url'], timeout=120) as response, partial.open('xb') as out:
            while True:
                block = response.read(262144)
                if not block:
                    break
                count += len(block)
                if count > 200_000_000:
                    raise ValueError('source archive exceeds bound')
                h.update(block)
                out.write(block)
        if count != source['size'] or h.hexdigest() != source['digests']['sha256']:
            raise ValueError('official source hash or size mismatch')
        partial.rename(path)
        return {'name': item['name'], 'version': item['version'], 'filename': filename,
                'url': source['url'], 'sha256': h.hexdigest(), 'bytes': count}

    results, failures = [], []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch, item): item['name'] for item in lock['artifacts']}
        for future in as_completed(futures):
            try:
                record = future.result()
                results.append(record)
                print(json.dumps({'verified_source': record['name'], 'bytes': record['bytes']}), flush=True)
            except Exception as error:
                failures.append({'name': futures[future], 'error': str(error)})
                print(json.dumps({'failed_source': futures[future], 'error': str(error)}), flush=True)
    with args.report.open('x', encoding='utf-8') as out:
        json.dump({'schema': 'clinical-pypi-source-lock@1.0', 'sources': sorted(results, key=lambda x:x['name']),
                   'failures': failures}, out, ensure_ascii=False, indent=2)
        out.write('\n')
    if failures:
        raise SystemExit(1)
    print(json.dumps({'status': 'PASS', 'verified_sources': len(results)}))


if __name__ == '__main__':
    main()
