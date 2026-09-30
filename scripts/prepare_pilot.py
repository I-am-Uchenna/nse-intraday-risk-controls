"""Stage selected instructor CSVs into a private SQLite database, one row at a time.

Requires the original instructor ZIP downloads and Windows bsdtar (tar).
Never extracts CSV files wholesale or includes their prices in public outputs.
"""
import argparse
from contextlib import contextmanager
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from path_robust.vendor import iter_vendor_rows


@contextmanager
def native_lines(archive, member=None):
    command = ['tar', '-tf', str(archive)] if member is None else ['tar', '-xOf', str(archive), member]
    with tempfile.TemporaryFile(mode='w+t', encoding='utf-8') as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                   text=True, encoding='utf-8-sig')
        try:
            yield process.stdout
            process.stdout.close()
            if process.wait():
                errors.seek(0)
                raise RuntimeError(errors.read(2000))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()


def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while block := source.read(1024*1024):
            digest.update(block)
    return digest.hexdigest()


def stage_outer(downloads, pattern, basename, cache):
    matches = []
    for path in sorted(downloads.glob(pattern)):
        with zipfile.ZipFile(path) as archive:
            for entry in archive.infolist():
                if Path(entry.filename).name == basename:
                    matches.append((path, entry.filename))
    if len(matches) != 1:
        raise ValueError(f'Expected one source for {basename}; found {len(matches)}')
    outer, member = matches[0]
    target = cache/basename
    digest = hashlib.sha256()
    with zipfile.ZipFile(outer) as archive, archive.open(member) as source, target.open('wb') as output:
        while block := source.read(1024*1024):
            output.write(block)
            digest.update(block)
    return target, {'outer_zip':outer.name, 'outer_member':member,
                    'nested_archive_sha256':digest.hexdigest(), 'outer_crc_checked':True}


def find_member(archive, basename):
    matches=[]
    with native_lines(archive) as lines:
        for line in lines:
            name=line.rstrip('\r\n')
            if Path(name).name == basename:
                matches.append(name)
    if len(matches)!=1:
        raise ValueError(f'Expected one {basename} in {archive.name}; found {len(matches)}')
    return matches[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--downloads',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,default=ROOT/'data/m4_pilot')
    parser.add_argument('--config',type=Path,default=ROOT/'config/m4_pilot.json')
    args=parser.parse_args()
    spec=json.loads(args.config.read_text(encoding='utf-8'))
    args.work_dir.mkdir(parents=True,exist_ok=True)
    cache=args.work_dir/'staged';cache.mkdir(exist_ok=True)
    database=args.work_dir/'pilot.sqlite'
    if database.exists():
        raise FileExistsError('Use a new work directory; existing pilot databases are preserved.')
    con=sqlite3.connect(database)
    con.execute('PRAGMA cache_size=-2048')
    con.execute('PRAGMA temp_store=FILE')
    con.execute('CREATE TABLE bars(symbol TEXT, stamp TEXT, o REAL,h REAL,l REAL,c REAL,volume REAL,source_id INTEGER,PRIMARY KEY(symbol,stamp)) WITHOUT ROWID')
    manifest=[]
    def ingest(archive, member, symbol, provenance):
        source_id=len(manifest)+1
        rows=0;first=None;last=None;digest=hashlib.sha256()
        with native_lines(archive,member) as lines:
            for record in iter_vendor_rows(lines,symbol):
                stamp=record.raw_timestamp.isoformat()
                if not spec['start_date'] <= stamp[:10] <= spec['end_date']:
                    raise ValueError(f'Unexpected date in pilot member: {stamp}')
                con.execute('INSERT INTO bars VALUES(?,?,?,?,?,?,?,?)',
                            (symbol,stamp,record.open,record.high,record.low,record.close,record.volume,source_id))
                digest.update(f'{symbol},{stamp},{record.open!r},{record.high!r},{record.low!r},{record.close!r},{record.volume!r}\n'.encode())
                rows+=1;first=first or stamp;last=stamp
        con.commit()
        manifest.append({**provenance,'archive':archive.name,'member':member,'symbol':symbol,
                         'rows':rows,'first_label':first,'last_label':last,
                         'parsed_ohlcv_sha256':digest.hexdigest()})
        print(json.dumps({'member':member,'rows':rows}),flush=True)

    try:
        for month in spec['pilot_months']:
            stock_archive,provenance=stage_outer(args.downloads,spec['raw_delivery_glob'],f'Cash Data {month} 2021.rar',cache)
            for symbol in spec['universe']:
                ingest(stock_archive,find_member(stock_archive,f'{symbol}.csv'),symbol,provenance)
        year,provenance=stage_outer(args.downloads,spec['raw_delivery_glob'],'NSE-Index-2021.7z',cache)
        for month in spec['pilot_months']:
            nested=find_member(year,f'NSE Indices-{month} 2021.rar')
            target=cache/Path(nested).name
            with target.open('wb') as out,tempfile.TemporaryFile(mode='w+t') as err:
                result=subprocess.run(['tar','-xOf',str(year),nested],stdout=out,stderr=err)
                if result.returncode:
                    err.seek(0);raise RuntimeError(err.read(2000))
            child_provenance={**provenance,'year_container_member':nested,'monthly_archive_sha256':hash_file(target)}
            ingest(target,find_member(target,'.NSEI.csv'),'.NSEI',child_provenance)
        diagnostics=[]
        for symbol in [*spec['universe'],spec['index_symbol']]:
            per_day=con.execute("SELECT substr(stamp,1,10),COUNT(*),SUM(substr(stamp,12)>='09:15:00' AND substr(stamp,12)<'15:30:00'),MIN(substr(stamp,12)),MAX(substr(stamp,12)) FROM bars WHERE symbol=? GROUP BY substr(stamp,1,10) ORDER BY 1",(symbol,)).fetchall()
            diagnostics.append({'symbol':symbol,'days':len(per_day),'rows':sum(r[1] for r in per_day),
                                'regular_label_rows':sum(r[2] for r in per_day),
                                'non_375_label_days':[r for r in per_day if r[2]!=375]})
        result={'protocol_sha256':hash_file(args.config),'input_files':manifest,'row_diagnostics':diagnostics,
                'database_prices_private':True,'assumptions':'raw labels retained; time zone and interval meaning unverified'}
        (args.work_dir/'input_audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'files':len(manifest),'rows':sum(x['rows'] for x in manifest),'database':str(database)}))
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


if __name__=='__main__':
    main()
