import os, sys, subprocess, shutil
from pathlib import Path

GAME_DIR = Path(__file__).parent.parent.parent.parent
CSC = r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
SOURCE_DIR = GAME_DIR / '.opencode' / 'skills' / 'build-translator' / 'source'
DATA_DIR = GAME_DIR / 'Third Crisis Neon Nights_Data' / 'Managed'
SOURCE_FILES = ['NativeMethods.cs', 'TranslationLoader.cs', 'MethodPatcher.cs', 'TranslatorPlugin.cs', 'NeonLateUpdate.cs']
REF_DLLS = ['UnityEngine.dll', 'UnityEngine.CoreModule.dll', 'UnityEngine.UI.dll', 'UnityEngine.UIModule.dll', 'UnityEngine.TextRenderingModule.dll', 'Unity.TextMeshPro.dll', 'netstandard.dll']

def main():
    print('NeonTranslatorRuntime — Build\n')
    for f in SOURCE_FILES:
        p = SOURCE_DIR / f
        if not p.exists():
            print(f'ERROR: missing source/{f}')
            sys.exit(1)
    print('  Source files: OK')

    refs = [DATA_DIR / r for r in REF_DLLS if (DATA_DIR / r).exists()]
    if len(refs) < 4:
        print('ERROR: Missing Unity assemblies')
        sys.exit(1)
    print(f'  Unity refs: {len(refs)} DLLs')

    out_dir = GAME_DIR / 'runtime'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'NeonTranslatorRuntime.dll'

    args = [
        '/target:library',
        f'/out:{out_path}',
        '/platform:x64',
        '/unsafe',
        '/nologo',
    ]
    for r in refs:
        args.append(f'/r:{r}')
    for f in SOURCE_FILES:
        args.append(str(SOURCE_DIR / f))

    print(f'  Compiler: {CSC}\n')
    result = subprocess.run([CSC] + args, capture_output=True, text=True, timeout=120, cwd=str(GAME_DIR))
    if result.returncode == 0:
        size = out_path.stat().st_size
        print(f'  OK: runtime/NeonTranslatorRuntime.dll ({size/1024:.1f} KB)')
    else:
        print('BUILD FAILED:')
        print(result.stdout or result.stderr or 'Unknown error')
        sys.exit(1)

if __name__ == '__main__':
    main()
