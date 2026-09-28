"""Backup/restore and build helpers. Credentials are never printed or put in argv.

Commands: backup, stage, replace. Replace requires successful verified backups
and a verified staging database. Intended for the explicitly requested reset.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import mysql.connector
from dotenv import dotenv_values, set_key

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BACKUPS = ROOT / 'database' / 'backups'
STAGE = 'college_simple_stage'
AUTH = 'college_auth'
TABLES = ['faculty', 'classes', 'courses', 'students', 'exams', 'results']


def config():
    return dotenv_values(ROOT / 'backend' / '.env')


def connect(database=None):
    c = config()
    return mysql.connector.connect(host=c['DB_HOST'], port=int(c.get('DB_PORT', 3306)),
                                   user=c['DB_USER'], password=c['DB_PASSWORD'],
                                   database=database, connection_timeout=10)


def cli(tool, args, *, source=None, destination=None):
    c = config()
    command = [shutil.which(tool) or str(Path('C:/Program Files/MySQL/MySQL Server 8.0/bin') / (tool + '.exe')),
               '--host=' + c['DB_HOST'], '--port=' + str(c.get('DB_PORT', 3306)),
               '--user=' + c['DB_USER'], '--default-character-set=utf8mb4', *args]
    env = dict(os.environ, MYSQL_PWD=c['DB_PASSWORD'])
    result = subprocess.run(command, stdin=source, stdout=destination or subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)
    if result.returncode:
        # MySQL diagnostics do not contain credentials; avoid command/environment repr.
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace'))


def fingerprint(database):
    conn = connect(database)
    cur = conn.cursor()
    try:
        cur.execute('SHOW FULL TABLES')
        tables = cur.fetchall()
        if any(kind != 'BASE TABLE' for _, kind in tables):
            raise RuntimeError('Backup verification needs explicit handling for views.')
        summary = {}
        for name, _ in tables:
            cur.execute('SHOW CREATE TABLE `' + name.replace('`', '``') + '`')
            ddl = cur.fetchone()[1]
            cur.execute('SELECT * FROM `' + name.replace('`', '``') + '`')
            rows = sorted(json.dumps(row, default=str, ensure_ascii=True) for row in cur.fetchall())
            summary[name] = dict(rows=len(rows), data_sha256=hashlib.sha256('\n'.join(rows).encode()).hexdigest(),
                                 ddl_sha256=hashlib.sha256(ddl.encode()).hexdigest())
        cur.execute('SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE()')
        return dict(tables=summary, triggers=cur.fetchone()[0])
    finally:
        cur.close()
        conn.close()


def dump(database, path):
    with path.open('wb') as out:
        cli('mysqldump', ['--single-transaction', '--skip-lock-tables', '--no-tablespaces',
                         '--routines', '--events', '--triggers', '--hex-blob',
                         '--set-gtid-purged=OFF', database], destination=out)


def load(database, path):
    with path.open('rb') as source:
        cli('mysql', [database], source=source)


def backup():
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = BACKUPS / stamp
    folder.mkdir(parents=True, exist_ok=False)
    conn = connect()
    cur = conn.cursor()
    manifest = {'created_at_utc': stamp, 'databases': {}}
    try:
        for database in ['college', 'college_v2']:
            cur.execute('SELECT schema_name FROM information_schema.schemata WHERE schema_name=%s', (database,))
            if not cur.fetchone():
                continue
            before = fingerprint(database)
            path = folder / (database + '.sql')
            dump(database, path)
            # Each backup is actually restored and compared before any original is dropped.
            restored = 'college_restore_check_' + database + '_' + stamp.lower()
            cur.execute(f'CREATE DATABASE `{restored}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
            load(restored, path)
            if fingerprint(restored) != before or fingerprint(database) != before:
                raise RuntimeError('Backup verification failed or source changed: ' + database)
            cur.execute(f'DROP DATABASE `{restored}`')  # only this tool-created verified restore
            manifest['databases'][database] = dict(path=str(path), fingerprint=before,
                                                  sha256=hashlib.sha256(path.read_bytes()).hexdigest(), restored_and_verified=True)
            print('Backed up and restore-verified:', database)
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (HERE / 'backup_location.txt').write_text(str(folder) + '\n')
        print('Backups:', folder)
    finally:
        cur.close()
        conn.close()


def stage():
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(f'CREATE DATABASE `{STAGE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
        load(STAGE, HERE / 'schema.sql')
        load(STAGE, HERE / 'seed.sql')
        print('Created six-table staging database:', STAGE)
    finally:
        cur.close()
        conn.close()


def replace():
    folder = Path((HERE / 'backup_location.txt').read_text().strip()).resolve()
    if not folder.is_relative_to(BACKUPS.resolve()):
        raise RuntimeError('Backup location is outside the expected backup directory.')
    manifest = json.loads((folder / 'manifest.json').read_text())
    for database, data in manifest['databases'].items():
        if database not in ('college', 'college_v2') or not data['restored_and_verified']:
            raise RuntimeError('Unexpected backup manifest entry.')
        if hashlib.sha256(Path(data['path']).read_bytes()).hexdigest() != data['sha256']:
            raise RuntimeError('Backup file changed.')
        if fingerprint(database) != data['fingerprint']:
            raise RuntimeError('Original database changed since backup. Make a fresh backup.')
    if 'college' not in manifest['databases']:
        raise RuntimeError('A verified college backup is required.')
    report = json.loads((HERE / 'verification.json').read_text())
    if report['database'] != STAGE or report['fingerprint'] != fingerprint(STAGE):
        raise RuntimeError('Staging schema/data must pass verification immediately before replacement.')
    conn = connect()
    cur = conn.cursor()
    try:
        # Keep the existing login records outside the six academic tables.
        cur.execute(f'CREATE DATABASE `{AUTH}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
        cur.execute(f'CREATE TABLE `{AUTH}`.app_users LIKE college.app_users')
        cur.execute(f'INSERT INTO `{AUTH}`.app_users SELECT * FROM college.app_users')
        conn.commit()
        if fingerprint(AUTH)['tables']['app_users']['data_sha256'] != manifest['databases']['college']['fingerprint']['tables']['app_users']['data_sha256']:
            raise RuntimeError('Authentication copy failed verification.')
        dump(STAGE, folder / 'college_simple_ready.sql')
        # Explicitly authorized database reset. The verified dump above is the rollback.
        cur.execute('DROP DATABASE `college`')
        cur.execute('CREATE DATABASE `college` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
        try:
            load('college', folder / 'college_simple_ready.sql')
            if fingerprint('college') != fingerprint(STAGE):
                raise RuntimeError('Replacement verification failed.')
        except Exception:
            cur.execute('DROP DATABASE `college`')
            cur.execute('CREATE DATABASE `college` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci')
            load('college', Path(manifest['databases']['college']['path']))
            raise
        set_key(str(ROOT / 'backend' / '.env'), 'DB_AUTH_NAME', AUTH)
        if 'college_v2' in manifest['databases']:
            cur.execute('DROP DATABASE `college_v2`')
        cur.execute(f'DROP DATABASE `{STAGE}`')
        print('Rebuilt college: six academic tables, 15 rows each.')
        print('Preserved login accounts in college_auth; removed college_v2 and staging.')
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['backup', 'stage', 'replace'])
    args = parser.parse_args()
    {'backup': backup, 'stage': stage, 'replace': replace}[args.command]()
