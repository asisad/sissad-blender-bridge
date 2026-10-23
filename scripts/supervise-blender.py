"""Local lifecycle supervision only. Never edits add-on source or scene files."""
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import msvcrt
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
from sissad_blender_bridge.lifecycle import lifecycle_action

SCRIPT = Path(__file__).resolve()
HERE = SCRIPT.parent if SCRIPT.parent.name == 'service' else SCRIPT.parents[1] / '.runtime/service'
CONFIG = json.loads((HERE / 'config.json').read_text(encoding='utf-8-sig'))
ROOT = Path(CONFIG['root'])
CREATION_FLAGS = subprocess.CREATE_NO_WINDOW
LOG = logging.getLogger('sissad_blender_service')
LOG.setLevel(logging.INFO)
handler = RotatingFileHandler(HERE / 'logs/supervisor.jsonl', maxBytes=CONFIG['max_log_bytes'], backupCount=CONFIG['log_backups'], encoding='utf-8')
handler.setFormatter(logging.Formatter('%(message)s'))
LOG.addHandler(handler)


def now():
    return datetime.now(timezone.utc).isoformat()


def event(kind, **fields):
    # Never log commands, environments, exceptions or upstream payloads containing secrets.
    LOG.info(json.dumps({'utc': now(), 'event': kind, **fields}, ensure_ascii=True))


def write_state(state):
    temp = HERE / f'state-{os.getpid()}.tmp'
    temp.write_text(json.dumps({'utc': now(), 'supervisor_pid': os.getpid(), **state}, indent=2), encoding='utf-8')
    temp.replace(HERE / 'state.json')


def native_json(args, timeout=30, env=None):
    try:
        result = subprocess.run([str(x) for x in args], cwd=ROOT, env=env, capture_output=True,
                                text=True, encoding='utf-8-sig', errors='replace', timeout=timeout,
                                creationflags=CREATION_FLAGS)
        try:
            payload = json.loads(result.stdout)
        except ValueError:
            payload = None
        return result.returncode, payload
    except subprocess.TimeoutExpired:
        return 124, None
    except OSError:
        return 125, None


class DataBlob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def runtime_key():
    # ConvertFrom-SecureString on Windows without -Key uses user-scoped DPAPI.
    encrypted = bytes.fromhex(Path(CONFIG['runtime_key_file']).read_text(encoding='ascii').strip())
    buffer = (ctypes.c_ubyte * len(encrypted)).from_buffer_copy(encrypted)
    source = DataBlob(len(encrypted), buffer)
    output = DataBlob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    decrypt = crypt.CryptUnprotectData
    decrypt.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
    decrypt.restype = wintypes.BOOL
    if not decrypt(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)):
        raise RuntimeError('credential_unavailable')
    try:
        return ctypes.string_at(output.pbData, output.cbData).decode('utf-16-le')
    finally:
        ctypes.memset(output.pbData, 0, output.cbData)
        free = ctypes.WinDLL('kernel32').LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(output.pbData)


def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=0.5):
            return True
    except OSError:
        return False


def blender_process_exists():
    # Observe the configured executable only. Never launch or stop Blender.
    cmd = "@(Get-CimInstance Win32_Process -Filter \"Name='blender.exe'\" | Select-Object -ExpandProperty ExecutablePath) | ConvertTo-Json -Compress"
    code, paths = native_json([CONFIG['pwsh'], '-NoProfile', '-Command', cmd], timeout=15)
    if code != 0:
        raise RuntimeError('process_inventory_unavailable')
    if isinstance(paths, str):
        paths = [paths]
    expected = json.loads((ROOT / 'config.local.json').read_text(encoding='utf-8-sig'))['profiles']['lab52']['env']['BLENDER_PATH']
    return any(str(p).casefold() == expected.casefold() for p in paths or [])


def process_image(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise RuntimeError('runtime_process_identity_unavailable')
    try:
        text, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(length)):
            raise RuntimeError('runtime_process_identity_unavailable')
        return Path(text.value).resolve()
    finally:
        kernel.CloseHandle(handle)


def stop_runtime(current):
    record = current.get('process', {})
    if (record.get('alias') != CONFIG['alias'] or record.get('tunnel_id') != CONFIG['tunnel_id'] or
        Path(record.get('profile_path', '')).resolve() != (Path(CONFIG['profile_dir']) / (CONFIG['alias'] + '.yaml')).resolve() or
        process_image(record.get('pid', 0)) != Path(CONFIG['tunnel_client']).resolve()):
        raise RuntimeError('runtime_identity_mismatch')
    code, _ = native_json([CONFIG['tunnel_client'], 'runtimes', 'stop', CONFIG['alias'], '--json'])
    if code:
        raise RuntimeError('runtime_stop_failed')
    event('runtime_stopped_blender_closed')


def status():
    _, result = native_json([CONFIG['tunnel_client'], 'runtimes', 'status', CONFIG['alias'], '--json'])
    return result or {}


def rotate_file(path, maximum=None):
    path = Path(path)
    maximum = maximum or CONFIG['max_log_bytes']
    if not path.is_file() or path.stat().st_size <= maximum:
        return False
    # Keep the open file handle valid: copy bounded tail then truncate in place.
    backups = CONFIG['log_backups']
    for index in range(backups, 1, -1):
        old = Path(str(path) + f'.{index - 1}')
        if old.exists():
            old.replace(Path(str(path) + f'.{index}'))
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - maximum))
        tail = stream.read(maximum)
    Path(str(path) + '.1').write_bytes(tail)
    with path.open('r+b') as stream:
        stream.truncate(0)
    return True


def connect():
    profile = Path(CONFIG['profile_dir']) / (CONFIG['alias'] + '.yaml')
    original = profile.read_bytes()
    parsed = json.loads(original.decode('utf-8-sig'))  # Existing generated JSON/YAML profile.
    if parsed['control_plane']['tunnel_id'] != CONFIG['tunnel_id']:
        raise RuntimeError('profile_identity_mismatch')
    environment = os.environ.copy()
    environment['CONTROL_PLANE_API_KEY'] = runtime_key()
    environment.update(LOG_LEVEL='warn', LOG_FILE=str(HERE / 'logs/tunnel.jsonl'), ADMIN_UI_LOG_BUFFER_EVENTS='200')
    try:
        code, result = native_json([CONFIG['tunnel_client'], 'runtimes', 'connect', '--alias', CONFIG['alias'],
            '--profile', CONFIG['alias'], '--profile-dir', CONFIG['profile_dir'], '--tunnel-id', CONFIG['tunnel_id'],
            '--runtime-api-key', parsed['control_plane']['api_key'], '--mcp-command', parsed['mcp']['commands'][0]['command'], '--json'],
            timeout=60, env=environment)
        event('connect_attempt', exit_code=code, healthy=bool((result or {}).get('healthy')), ready=bool((result or {}).get('ready')))
        return code, result or {}
    finally:
        environment.pop('CONTROL_PLANE_API_KEY', None)
        # Preserve every original setting and exact bytes, even if CLI regenerated formatting.
        if profile.read_bytes() != original:
            profile.write_bytes(original)
            event('original_profile_preserved', sha256=hashlib.sha256(original).hexdigest())


def local_probe():
    code, response = native_json([ROOT / '.venv/Scripts/sissad-blender.exe', '--config', ROOT / 'config.local.json',
        'call', '--profile', 'community52', '--timeout', '15', '--tool', 'execute_blender_code',
        '--arguments-file', HERE / 'read-only-probe.json'], timeout=25)
    if code == 0 and response and response.get('ok'):
        for block in response.get('result', {}).get('content', []):
            if block.get('type') == 'text':
                for line in block.get('text', '').splitlines():
                    start = line.find('{')
                    if start >= 0:
                        try:
                            value = json.loads(line[start:])
                            if value.get('probe') == 'sissad-local-health-v1' and value.get('version', '').startswith('5.2.'):
                                return {'ok': True, 'observed_utc': now(), **value}
                        except ValueError:
                            pass
    return {'ok': False, 'exit_code': code, 'error_code': (response or {}).get('error', {}).get('code', 'semantic_probe_failed')}


def main(once=False):
    lock = (HERE / 'supervisor.lock').open('a+b')
    lock.seek(0, 2)
    if lock.tell() == 0:
        lock.write(b'0')
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        print(json.dumps({'status': 'already_running'}))
        lock.close()
        return 0
    event('supervisor_started', pid=os.getpid())
    failures, next_retry, last_probe, probe, last_phase = 0, 0, -9999, {}, None
    last_tunnel_pid, stable_since = None, time.monotonic()
    try:
        while not (HERE / 'stop.request').exists():
            state = {'alias': CONFIG['alias'], 'blender_ready': False}
            try:
                present = blender_process_exists()
                ready = present and port_open(9876) and port_open(9877)
                state.update(blender_running=present, blender_ready=ready, auto_launch_blender=False)
                current = status()
                action = lifecycle_action(blender_running=present, local_ready=ready,
                    runtime_running=bool(current.get('process_running')), retry_due=time.monotonic() >= next_retry)
                if action == 'stop':
                    stop_runtime(current)
                    current = status()
                if not present:
                    failures, next_retry, last_tunnel_pid, probe = 0, 0, None, {}
                if not current.get('process_running') and last_tunnel_pid is not None:
                    failures += 1
                    delay = CONFIG['retry_seconds'][min(failures - 1, len(CONFIG['retry_seconds']) - 1)]
                    next_retry = time.monotonic() + delay
                    event('runtime_lost', previous_pid=last_tunnel_pid, retry_seconds=delay, failures=failures)
                    last_tunnel_pid = None
                if not current.get('process_running') and time.monotonic() >= next_retry and ready:
                    connect()
                    current = status()
                    if not current.get('process_running'):
                        failures += 1
                        delay = CONFIG['retry_seconds'][min(failures - 1, len(CONFIG['retry_seconds']) - 1)]
                        next_retry = time.monotonic() + delay
                        event('retry_scheduled', delay_seconds=delay, failures=failures)
                running = bool(current.get('process_running'))
                if running:
                    current_pid = current.get('process', {}).get('pid')
                    if current_pid != last_tunnel_pid:
                        stable_since = time.monotonic()
                    last_tunnel_pid = current_pid
                if running and current.get('healthy') and current.get('ready'):
                    if time.monotonic() - stable_since >= 120:
                        failures = 0
                    if ready and time.monotonic() - last_probe >= CONFIG['local_probe_seconds']:
                        probe = local_probe()
                        last_probe = time.monotonic()
                        event('community52_read', ok=probe.get('ok'), version=probe.get('version'))
                state.update(tunnel_pid=current.get('process', {}).get('pid'), process_running=running,
                             healthy=bool(current.get('healthy')), ready=bool(current.get('ready')),
                             health_url=current.get('health_url'), last_blender_read=probe,
                             retry_in_seconds=max(0, round(next_retry - time.monotonic())), failures=failures)
                state['phase'] = ('waiting_blender' if not present else
                    ('waiting_local_bridge' if not ready else
                    ('ready' if state['healthy'] and state['ready'] and probe.get('ok') else
                    ('local_probe_failed' if running and not probe.get('ok') else 'retry_wait'))))
                # Network/429 failures belong to tunnel-client's own spaced poll backoff.
                # Never cycle a live tunnel or alter keys/firewall to bypass them.
                for file in (HERE / 'logs/tunnel.jsonl', Path(os.environ['USERPROFILE']) / '.local/state/tunnel-client/logs' / (CONFIG['alias'] + '.log')):
                    try:
                        rotate_file(file)
                    except OSError:
                        event('log_rotation_deferred', file=file.name)
            except Exception as error:
                failures += 1
                delay = CONFIG['retry_seconds'][min(failures - 1, len(CONFIG['retry_seconds']) - 1)]
                next_retry = time.monotonic() + delay
                state.update(phase='retry_wait', error_type=type(error).__name__, failures=failures, retry_in_seconds=delay)
                frames = [{'file': Path(frame.filename).name, 'line': frame.lineno, 'function': frame.name}
                          for frame in traceback.extract_tb(error.__traceback__)]
                event('supervisor_check_failed', error_type=type(error).__name__, retry_seconds=delay, frames=frames,
                      missing_file=getattr(error, 'filename', None), windows_error=getattr(error, 'winerror', None))
            if state.get('phase') != last_phase:
                event('phase_changed', phase=state.get('phase'))
                last_phase = state.get('phase')
            write_state(state)
            if once:
                print(json.dumps(state))
                break
            time.sleep(CONFIG['poll_seconds'])
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()
        event('supervisor_stopped', pid=os.getpid())
    return 0


if __name__ == '__main__':
    args = argparse.ArgumentParser()
    args.add_argument('--once', action='store_true')
    options = args.parse_args()
    sys.exit(main(options.once))
