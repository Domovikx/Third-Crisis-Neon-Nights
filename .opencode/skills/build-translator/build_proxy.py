import os, sys, subprocess, shutil
from pathlib import Path

GAME_DIR = Path(__file__).parent.parent.parent.parent
MSVC_TOOLS = r'C:/Program Files (x86)/Microsoft Visual Studio/18/BuildTools/VC/Tools/MSVC/14.50.35717'
CL = Path(MSVC_TOOLS) / 'bin/Hostx64/x64/cl.exe'
SDK = r'C:/Program Files (x86)/Windows Kits/10'
SDK_VER = '10.0.26100.0'

INCLUDES = [
    Path(MSVC_TOOLS) / 'include',
    Path(SDK) / 'Include' / SDK_VER / 'shared',
    Path(SDK) / 'Include' / SDK_VER / 'um',
    Path(SDK) / 'Include' / SDK_VER / 'ucrt',
]
LIBS = [
    Path(MSVC_TOOLS) / 'lib' / 'x64',
    Path(SDK) / 'Lib' / SDK_VER / 'ucrt' / 'x64',
    Path(SDK) / 'Lib' / SDK_VER / 'um' / 'x64',
]

SOURCE = GAME_DIR / '.opencode' / 'skills' / 'build-translator' / 'source' / 'dwmapi_proxy.c'
OUT_PATH = GAME_DIR / 'dwmapi.dll'
REAL_COPY = GAME_DIR / 'dwmapi_real.dll'

def main():
    print('dwmapi.dll — Build (Native Proxy)\n')

    system_root = os.environ.get('SystemRoot', r'C:\Windows')
    system_dwmapi = Path(system_root) / 'System32' / 'dwmapi.dll'
    print(f'  Real dwmapi: {system_dwmapi}')
    try:
        shutil.copy2(str(system_dwmapi), str(REAL_COPY))
        print('  -> dwmapi_real.dll copied to game root')
    except Exception as e:
        print(f'  FAILED to copy dwmapi_real.dll: {e}')
        sys.exit(1)

    for old in ['version.dll', 'version_proxy.c', 'winhttp.dll']:
        p = GAME_DIR / old
        try:
            p.unlink()
            print(f'  Removed old: {old}')
        except:
            pass

    if not SOURCE.exists():
        print('ERROR: missing source/dwmapi_proxy.c')
        sys.exit(1)
    if not CL.exists():
        print(f'ERROR: cl.exe not found at {CL}')
        sys.exit(1)
    print(f'  Compiler: {CL}')

    args = [
        str(CL),
        '/nologo', '/O1', '/MD', '/LD', '/UTF-8',
        f'/Fe{OUT_PATH}',
    ]
    for p in INCLUDES:
        args.append(f'/I{p}')
    args.append(str(SOURCE))
    args.append('/link')
    for p in LIBS:
        args.append(f'/LIBPATH:{p}')
    args.append('/MACHINE:X64')
    args.append('kernel32.lib')

    print('  Compiling...\n')
    result = subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=str(GAME_DIR))

    if result.returncode == 0:
        size = OUT_PATH.stat().st_size
        print(f'  OK: dwmapi.dll ({size/1024:.1f} KB)')
        real_size = REAL_COPY.stat().st_size
        print(f'  OK: dwmapi_real.dll ({real_size/1024:.1f} KB) — forwarder target')
        print('\n  Restart game to load the new proxy!')
    else:
        print('BUILD FAILED:')
        print(result.stdout or result.stderr or 'Unknown error')
        sys.exit(1)

if __name__ == '__main__':
    main()
