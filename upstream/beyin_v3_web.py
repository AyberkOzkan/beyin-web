"""Beyin'in istege bagli web arayuzu (beyin-web) icin ince baslatici.

    python3 beyin.py web kur [--paket ZIP] [--kisayol-yok] [--dil tr|en]
    python3 beyin.py web ac
    python3 beyin.py web durum
    python3 beyin.py web kaldir

Arayuzun kodu bu dosyada degildir. `kur` asagida sabitlenen surumun ZIP'ini indirir (ya da --paket ile
verileni okur), SHA-256 ozetini dogrular, durum klasorunde web/<surum>/ altina acar ve bir kisayol birakir.
Vault'a hicbir sey yazilmaz; `kur` cagrilmadikca ag istegi yapilmaz. `beyin.py` bu alt komutu tanimadan
once dosya tek basina da calisir:

    python3 beyin_v3_web.py --vault ~/Beyin kur --paket beyin-web-0.2.0.zip
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

VERSION = '0.2.0'
SHA256 = '6744a5bac61f9dc90e510e34f8b5c85ec42e7ddb641ce73880382a6dbe52b62c'
URL = 'https://github.com/AyberkOzkan/beyin-web/releases/download/v{version}/beyin-web-{version}.zip'
FOLDER = 'web'
STATE_FILE = 'web.json'
MAX_BYTES = 20 * 1024 * 1024
MIN_PYTHON = (3, 11)
# What a release holds: the package and the files that say what it is. Anything else is refused.
TOP_LEVEL = {'LICENSE', 'README.md', 'CHANGELOG.md'}
DESCRIPTION = {'tr': "Beyin'in web arayüzünü açar", 'en': 'Opens the web interface of Beyin'}

# Runs inside the installed copy, so the shortcut is written by the code it starts and this file stays small.
SHORTCUT_CODE = '''import json, sys
from pathlib import Path
from beyin_web import install
request = json.load(sys.stdin)
if request["remove"]:
    paths = install.remove_shortcuts()
else:
    paths = install.write_shortcuts(Path(request["app"]), arguments=request["arguments"],
                                    description=request["description"])
json.dump(paths, sys.stdout)
'''
RUNNING_CODE = '''import json, sys
from pathlib import Path
from beyin_web.__main__ import find_running
from beyin_web.config import config_directory, load_settings
settings = load_settings(Path(sys.argv[1]), config_directory())
json.dump(find_running(settings), sys.stdout)
'''


# ---------------------------------------------------------------- state

def default_state(vault):
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / 'AppData/Local')))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    return base / 'beyin-v3' / hashlib.sha256(str(vault).encode()).hexdigest()[:16]


def resolve_state(vault):
    config = Path(vault) / '.beyin-runtime.json'
    try:
        pinned = Path(json.loads(config.read_text(encoding='utf-8'))['state']).expanduser()
    except (OSError, ValueError, KeyError, TypeError):
        pinned = None
    # A pin from another OS through a synced vault is not absolute here (#249).
    return pinned if pinned and pinned.is_absolute() else default_state(Path(vault).resolve())


def _state_path(state):
    return Path(state) / STATE_FILE


def read_state(state):
    try:
        value = json.loads(_state_path(state).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _installed(state):
    record = read_state(state)
    app = Path(state) / FOLDER / str(record.get('surum')) if record else None
    if not app or not (app / 'beyin_web' / '__main__.py').is_file():
        raise ValueError('beyin-web kurulu degil. Kurmak icin: beyin.py web kur')
    return record, app


# ---------------------------------------------------------------- package

def download(url):
    import urllib.request
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Indirilen paket beklenenden buyuk; kurulum durduruldu.')
    return data


def verified(data, expected=None):
    expected = expected or SHA256
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError('Paketin SHA-256 ozeti tutmuyor; kurulum durduruldu.\n  beklenen: ' + expected +
                         '\n  gelen:    ' + actual)
    return data


def _member(name):
    path = PurePosixPath(name)
    if (not name or '\\' in name or path.is_absolute() or '..' in path.parts or ':' in path.parts[0]
            or not (path.parts[0] == 'beyin_web' or (len(path.parts) == 1 and name in TOP_LEVEL))):
        raise ValueError('Pakette beklenmeyen bir dosya var: ' + name)
    return path


def unpack(data, target):
    """Open the archive into ``target`` through a staging folder; a broken archive leaves the old copy in place."""
    target = Path(target)
    staging = target.with_name(target.name + '.new')
    shutil.rmtree(staging, ignore_errors=True)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [entry for entry in archive.infolist() if not entry.is_dir()]
            for entry in members:
                path = _member(entry.filename)
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Pakette baglanti (symlink) var: ' + entry.filename)
                destination = staging.joinpath(*path.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, open(destination, 'wb') as sink:
                    shutil.copyfileobj(source, sink)
    except zipfile.BadZipFile:
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError('Paket okunamadi (bozuk ZIP).')
    except ValueError:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if not (staging / 'beyin_web' / '__main__.py').is_file():
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError('Pakette beyin_web yok.')
    shutil.rmtree(target, ignore_errors=True)
    staging.replace(target)
    return target


# ---------------------------------------------------------------- commands

def launch_arguments(vault, language=None):
    """What the shortcut and `ac` run: the vault Beyin already knows, a reused server, a self-closing idle one."""
    arguments = ['-m', 'beyin_web', '--vault', str(vault), '--open', '--reuse', '--idle-exit', '30']
    return arguments + (['--lang', language] if language else [])


def _python_env():
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['PYTHONUTF8'] = '1'
    return environment


def _in_app(app, code, request=None, arguments=(), python=None, env=None):
    result = subprocess.run([python or sys.executable, '-c', code, *arguments], cwd=str(app),
                            input=json.dumps(request) if request is not None else '', env=env or _python_env(),
                            capture_output=True, encoding='utf-8', errors='replace', timeout=120, check=False)
    if result.returncode != 0:
        raise OSError(result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'exit ' + str(result.returncode))
    return json.loads(result.stdout or 'null')


def install(vault, state, package=None, shortcut=True, language=None, env=None):
    if sys.version_info < MIN_PYTHON:
        raise ValueError('beyin-web Python %d.%d ya da yenisini ister; bu Python %d.%d.' %
                         (MIN_PYTHON + tuple(sys.version_info[:2])))
    vault, state = Path(vault).resolve(), Path(state).resolve()
    data = verified(Path(package).read_bytes() if package else download(URL.format(version=VERSION)))
    folder = state / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    app = unpack(data, folder / VERSION)
    for other in folder.iterdir():
        if other.is_dir() and other.name != VERSION:
            shutil.rmtree(other, ignore_errors=True)
    done = {'status': 'kuruldu', 'surum': VERSION, 'klasor': str(app), 'kisayol': [], 'kisayol_hatasi': None}
    if shortcut:
        try:
            done['kisayol'] = _in_app(app, SHORTCUT_CODE, {
                'remove': False, 'app': str(app), 'arguments': launch_arguments(vault, language),
                'description': DESCRIPTION.get(language or 'tr', DESCRIPTION['tr'])}, env=env)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            done['kisayol_hatasi'] = str(error)
    _state_path(state).write_text(json.dumps({'schema': 1, 'surum': VERSION, 'sha256': SHA256, 'dil': language,
                                              'kisayol': done['kisayol']}, ensure_ascii=False) + '\n', encoding='utf-8')
    return done


def open_interface(vault, state):
    record, app = _installed(state)
    return subprocess.call([sys.executable, *launch_arguments(Path(vault).resolve(), record.get('dil'))],
                           cwd=str(app), env=_python_env())


def status(vault, state, env=None):
    try:
        record, app = _installed(state)
    except ValueError:
        return {'status': 'tamam', 'kurulu': False, 'surum': None, 'beklenen_surum': VERSION, 'guncel': False,
                'klasor': None, 'kisayol': [], 'calisiyor': None}
    try:
        port = _in_app(app, RUNNING_CODE, arguments=[str(Path(vault).resolve())], env=env)
    except (OSError, ValueError, subprocess.SubprocessError):
        port = None
    return {'status': 'tamam', 'kurulu': True, 'surum': record.get('surum'), 'beklenen_surum': VERSION,
            'guncel': record.get('surum') == VERSION and record.get('sha256') == SHA256, 'klasor': str(app),
            'kisayol': record.get('kisayol') or [], 'calisiyor': port}


def uninstall(vault, state, env=None):
    state = Path(state).resolve()
    removed = []
    record = read_state(state)
    app = state / FOLDER / str(record.get('surum')) if record else None
    if app and (app / 'beyin_web' / '__main__.py').is_file() and record.get('kisayol'):
        try:
            removed += _in_app(app, SHORTCUT_CODE, {'remove': True}, env=env)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    if (state / FOLDER).exists():
        shutil.rmtree(state / FOLDER)
        removed.append(FOLDER + '/')
    if _state_path(state).exists():
        _state_path(state).unlink()
        removed.append(STATE_FILE)
    return {'status': 'kaldirildi', 'kaldirilan': removed, 'vault_korundu': True}


# ---------------------------------------------------------------- CLI

def human(result, command):
    if command == 'kur':
        lines = ['beyin-web ' + result['surum'] + ' kuruldu: ' + result['klasor']]
        if result['kisayol']:
            lines.append('Kisayol: ' + ', '.join(result['kisayol']))
        elif result['kisayol_hatasi']:
            lines.append('UYARI: kisayol yazilamadi (' + result['kisayol_hatasi'] + ').')
        lines.append('Acmak icin: beyin.py web ac')
        return '\n'.join(lines)
    if command == 'kaldir':
        return 'beyin-web kaldirildi. Vault ve ayarlar yerinde duruyor.'
    if command == 'durum':
        if not result['kurulu']:
            return 'Kurulu: hayir\nKurmak icin: beyin.py web kur'
        return ('Kurulu: evet (' + str(result['surum']) + ('' if result['guncel'] else ', beklenen ' + result['beklenen_surum']) + ')' +
                '\nKlasor: ' + result['klasor'] +
                '\nKisayol: ' + (', '.join(result['kisayol']) or 'yok') +
                '\nCalisiyor: ' + ('evet, http://127.0.0.1:' + str(result['calisiyor']) + '/' if result['calisiyor'] else 'hayir'))
    return json.dumps(result, ensure_ascii=False, indent=2)


def find_vault(given):
    if given:
        return Path(given).expanduser()
    # Inside a vault this file sits at .claude/scripts/; the vault is two folders up.
    here = Path(__file__).resolve().parents[2]
    return here if (here / 'beyin.py').is_file() else None


def main(argv=None, vault=None, state=None):
    def shared(default):
        # Subcommands must not reset a --vault/--json given before them, hence SUPPRESS there.
        common = argparse.ArgumentParser(add_help=False)
        common.add_argument('--vault', type=Path, dest='vault_sub', default=default, help=argparse.SUPPRESS)
        common.add_argument('--json', action='store_true', dest='force_json',
                            default=False if default is None else default, help=argparse.SUPPRESS)
        return common
    parser = argparse.ArgumentParser(prog='beyin.py web', description="Beyin'in web arayuzunu kur ve ac",
                                     parents=[shared(None)])
    sub = parser.add_subparsers(dest='command')
    common = shared(argparse.SUPPRESS)
    setup = sub.add_parser('kur', parents=[common], help='Sabitlenen surumu indir, dogrula, kur; kisayol birak')
    setup.add_argument('--paket', type=Path, help='Indirmek yerine bu ZIP dosyasini kullan (ozeti yine dogrulanir)')
    setup.add_argument('--kisayol-yok', action='store_true', help='Kisayol birakma')
    setup.add_argument('--dil', choices=('tr', 'en'), help='Arayuzun dili (varsayilan Turkce)')
    sub.add_parser('ac', parents=[common], help='Arayuzu bu vault ile ac')
    sub.add_parser('durum', parents=[common], help='Kurulu mu, hangi surum, calisiyor mu')
    sub.add_parser('kaldir', parents=[common], help='Kisayolu ve kurulu kopyayi sil; vault\'a dokunmaz')
    args = parser.parse_args(argv)
    vault = vault or find_vault(args.vault_sub)
    if vault is None:
        parser.error('--vault gerekli')
    vault = Path(vault).expanduser().resolve()
    if not vault.is_dir():
        raise ValueError('Vault bulunamadi: ' + str(vault))
    state = Path(state) if state else resolve_state(vault)
    command = args.command or 'durum'
    if command == 'ac':
        return open_interface(vault, state)
    if command == 'kur':
        result = install(vault, state, package=args.paket, shortcut=not args.kisayol_yok, language=args.dil)
    elif command == 'kaldir':
        result = uninstall(vault, state)
    else:
        result = status(vault, state)
    if sys.stdout is None:
        return 0
    as_json = args.force_json or not sys.stdout.isatty()
    print(json.dumps(result, ensure_ascii=False, indent=2) if as_json else human(result, command))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ValueError as exc:
        if sys.stderr:
            print(str(exc), file=sys.stderr)
        raise SystemExit(1)
