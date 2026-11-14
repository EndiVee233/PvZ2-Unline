"""Back up Android game saves before tests and restore the same baseline afterward."""
from pathlib import Path, PurePosixPath
import datetime
import hashlib
import io
import json
import subprocess
import sys
import os
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'work/private-save-backups'
ACTIVE = STORE / 'ACTIVE.json'
ADB = os.environ.get('PVZ2_ADB', 'Y:/Android/Sdk/platform-tools/adb.exe')
PACKAGE = os.environ.get('PVZ2_PACKAGE', 'com.pvz2unline.aster')
PATHS = ['files/userdata', 'files/userdataNo_Backup', 'shared_prefs', 'databases']
EXTERNAL_FILES = f'/sdcard/Android/data/{PACKAGE}/files'
LEVEL_DIR = 'pvp_level'


def call(*args):
    return subprocess.run([ADB, *args], check=True, capture_output=True, timeout=90).stdout


def inspect_archive(raw, paths=PATHS):
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        files = {}
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not any(
                member.name == p or member.name.startswith(p + '/') for p in paths
            ):
                raise ValueError('Archive path outside the fixed save directories')
            if not (member.isdir() or member.isfile()):
                raise ValueError('Unexpected archive link or special file')
            if member.isfile():
                files[member.name] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        if paths == PATHS and 'files/userdataNo_Backup/pp.dat' not in files:
            raise ValueError('Player save missing from archive')
        return files


def stop():
    call('shell', 'am', 'force-stop', PACKAGE)


def capture():
    return call('exec-out', 'run-as', PACKAGE, 'tar', '-cf', '-', *PATHS)


def capture_levels():
    path = f'{EXTERNAL_FILES}/{LEVEL_DIR}'
    # WSA can expose the package directory to shell while hiding its app-owned files.
    probe = subprocess.run([ADB, 'shell', f"su -c 'test -d {path}'"], capture_output=True, timeout=90)
    if probe.returncode == 1 and not probe.stderr:
        return None
    probe.check_returncode()
    raw = call('exec-out', 'su', '-c', f'tar -cf - -C {EXTERNAL_FILES} {LEVEL_DIR}')
    if len(raw) % 512 or not raw.endswith(bytes(1024)):
        raise ValueError('Incomplete PvP level archive')
    return raw


def stamp():
    return datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')


def backup():
    STORE.mkdir(parents=True, exist_ok=True)
    if ACTIVE.exists():
        state = json.loads(ACTIVE.read_text(encoding='utf8'))
        if state.get('status') == 'pending_restore':
            print(json.dumps({'reused_pending_snapshot': state['snapshot']}))
            return
    stop()
    raw = capture()
    files = inspect_archive(raw)
    levels = capture_levels()
    folder = STORE / (stamp() + '-before-test')
    folder.mkdir()
    (folder / 'saves.tar').write_bytes(raw)
    metadata = dict(snapshot=str(folder), package=PACKAGE, paths=PATHS,
                    sha256=hashlib.sha256(raw).hexdigest(), files=files,
                    status='pending_restore')
    metadata['pvp_level'] = None
    if levels is not None:
        metadata['pvp_level'] = dict(sha256=hashlib.sha256(levels).hexdigest(),
                                     files=inspect_archive(levels, [LEVEL_DIR]))
        (folder / 'pvp-level.tar').write_bytes(levels)
    (folder / 'manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
    ACTIVE.write_text(json.dumps(dict(snapshot=str(folder), status='pending_restore'), indent=2), encoding='utf8')
    print(json.dumps(dict(snapshot=str(folder), files=len(files), backup_verified=True)))


def restore():
    state = json.loads(ACTIVE.read_text(encoding='utf8'))
    if state.get('status') != 'pending_restore':
        raise ValueError('No pending test baseline to restore')
    folder = Path(state['snapshot']).resolve()
    if not folder.is_relative_to(STORE.resolve()):
        raise ValueError('Snapshot outside private backup directory')
    metadata = json.loads((folder / 'manifest.json').read_text(encoding='utf8'))
    raw = (folder / 'saves.tar').read_bytes()
    if metadata['package'] != PACKAGE or metadata['paths'] != PATHS:
        raise ValueError('Snapshot package or directory mismatch')
    if hashlib.sha256(raw).hexdigest() != metadata['sha256']:
        raise ValueError('Backup checksum mismatch')
    baseline = inspect_archive(raw)
    if baseline != metadata['files']:
        raise ValueError('Backup file manifest mismatch')
    level_state = metadata.get('pvp_level')
    levels = None
    if level_state is not None:
        levels = (folder / 'pvp-level.tar').read_bytes()
        if hashlib.sha256(levels).hexdigest() != level_state['sha256'] or (
            inspect_archive(levels, [LEVEL_DIR]) != level_state['files']
        ):
            raise ValueError('PvP level backup verification failed')
    stop()
    # Keep the complete test state as a second recovery option before replacement.
    current = capture()
    inspect_archive(current)
    (folder / ('before-restore-' + stamp() + '.tar')).write_bytes(current)
    remote = '/data/local/tmp/pvz2-test-save-restore.tar'
    call('push', str(folder / 'saves.tar'), remote)
    try:
        call('shell', 'chmod', '644', remote)
        # Fixed relative paths in this package's private directory; never a computed target.
        call('shell', 'run-as', PACKAGE, 'rm', '-rf', *PATHS)
        call('shell', 'run-as', PACKAGE, 'tar', '-xf', remote)
        restored = inspect_archive(capture())
        if restored != baseline:
            raise ValueError('Restore did not match every baseline file')
    finally:
        call('shell', 'rm', '-f', remote)
    if 'pvp_level' in metadata:
        restore_levels(folder, levels, level_state)
    # An explicitly prepared decoder probe may temporarily hide one generated
    # cache entry. Restore it with the save baseline; never accept arbitrary
    # paths from a test record as shell operands.
    probe = folder / 'decode-cache-probe.json'
    if probe.is_file():
        record = json.loads(probe.read_text(encoding='utf8'))
        original, held = record['original'], record['held']
        if not re.fullmatch(r'cache/glcache/[0-9a-f]{16}\.rgba', original) or held != original + '.v165-held':
            raise ValueError('Unexpected generated texture cache probe path')
        call('shell', 'run-as', PACKAGE, 'mv', held, original)
        probe.rename(folder / 'decode-cache-probe-restored.json')
    state.update(status='restored', verified_files=len(restored), restored_at=stamp())
    ACTIVE.write_text(json.dumps(state, indent=2), encoding='utf8')
    (folder / 'restore-verification.json').write_text(json.dumps(state, indent=2), encoding='utf8')
    print(json.dumps(dict(restored=True, verified_files=len(restored), game_stopped=True)))


def retain():
    """Finish a batch without rollback only on the user's explicit request.

    Retain the old baseline and capture the actual played state as a second
    recovery point. No player save or external level is replaced or removed.
    The next backup must therefore start from the newly retained game state.
    """
    state = json.loads(ACTIVE.read_text(encoding='utf8'))
    if state.get('status') != 'pending_restore':
        raise ValueError('No pending test batch to retain')
    folder = Path(state['snapshot']).resolve()
    if not folder.is_relative_to(STORE.resolve()):
        raise ValueError('Snapshot outside private backup directory')
    metadata = json.loads((folder / 'manifest.json').read_text(encoding='utf8'))
    if metadata['package'] != PACKAGE or metadata['paths'] != PATHS:
        raise ValueError('Snapshot package or directory mismatch')
    if (folder / 'decode-cache-probe.json').exists():
        raise ValueError('Restore the explicitly held generated cache before retaining')
    stop()
    current = capture()
    files = inspect_archive(current)
    levels = capture_levels()
    (folder / 'retained-state.tar').write_bytes(current)
    detail = dict(user_requested_no_rollback=True, package=PACKAGE,
                  sha256=hashlib.sha256(current).hexdigest(), files=files,
                  retained_at=stamp(), pvp_level=None)
    if levels is not None:
        (folder / 'retained-levels.tar').write_bytes(levels)
        detail['pvp_level'] = dict(sha256=hashlib.sha256(levels).hexdigest(),
                                   files=inspect_archive(levels, [LEVEL_DIR]))
    (folder / 'retained-by-user.json').write_text(json.dumps(detail, indent=2), encoding='utf8')
    state.update(status='retained_by_user', retained_at=detail['retained_at'],
                 reason='Explicit user instruction: preserve actual WSA USER play, no rollback')
    ACTIVE.write_text(json.dumps(state, indent=2), encoding='utf8')
    print(json.dumps(dict(retained=True, rollback_performed=False, captured_files=len(files),
                         original_baseline_preserved=True, game_stopped=True)))


def restore_levels(folder, levels, level_state):
    current = capture_levels()
    if current is not None:
        inspect_archive(current, [LEVEL_DIR])
        (folder / ('levels-before-restore-' + stamp() + '.tar')).write_bytes(current)
    remote = '/data/local/tmp/pvz2-test-levels-restore.tar'
    if levels is not None:
        call('push', str(folder / 'pvp-level.tar'), remote)
    try:
        call('shell', f"su -c 'rm -rf {EXTERNAL_FILES}/{LEVEL_DIR}'")
        if levels is not None:
            call('shell', f"su -c 'tar -xf {remote} -C {EXTERNAL_FILES}'")
        verified = capture_levels()
        if levels is None:
            if verified is not None:
                raise ValueError('PvP level directory should be absent after restore')
        elif verified is None or inspect_archive(verified, [LEVEL_DIR]) != level_state['files']:
            raise ValueError('Restore did not match every PvP level file')
    finally:
        if levels is not None:
            call('shell', 'rm', '-f', remote)


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('backup', 'restore', 'retain'):
        raise SystemExit('Usage: python scripts/wsa_save_snapshot.py backup|restore|retain')
    {'backup': backup, 'restore': restore, 'retain': retain}[sys.argv[1]]()
