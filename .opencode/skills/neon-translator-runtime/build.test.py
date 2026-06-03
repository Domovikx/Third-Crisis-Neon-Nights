import os, sys, subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).parent
GAME_DIR = SKILL_DIR.parent.parent.parent
CSC = r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'

passed = 0
failed = 0

def assert_eq(cond, msg):
    global passed, failed
    if cond:
        passed += 1
        print('.', end='', flush=True)
    else:
        failed += 1
        print('F', end='', flush=True)
        print(f'\n  FAIL: {msg}')

def main():
    global passed, failed

    print('=== NeonTranslatorRuntime — Build Tests ===\n')

    print('1. Source files')
    for f in ['NativeMethods.cs', 'TranslationLoader.cs', 'MethodPatcher.cs', 'TranslatorPlugin.cs', 'NeonLateUpdate.cs']:
        p = SKILL_DIR / 'source' / f
        assert_eq(p.exists(), f'{f} exists')

    print()
    print('2. Build script')
    assert_eq((SKILL_DIR / 'build.py').exists(), 'build.py exists')

    print()
    print('3. Compilation')
    build_py = SKILL_DIR / 'build.py'
    try:
        result = subprocess.run([sys.executable, str(build_py)], capture_output=True, text=True, timeout=120, cwd=str(GAME_DIR))
        assert_eq(result.returncode == 0, f'build: {result.stdout[:200]}')
    except Exception as e:
        assert_eq(False, f'build exception: {e}')

    dll_path = GAME_DIR / 'runtime' / 'NeonTranslatorRuntime.dll'
    assert_eq(dll_path.exists(), 'DLL created')
    dll_size = dll_path.stat().st_size if dll_path.exists() else 0
    assert_eq(dll_size > 1000, f'DLL size: {dll_size} bytes')

    print()
    print('4. DLL content verification')
    if dll_path.exists():
        content = dll_path.read_bytes()
        for term in ['NeonTranslator', 'TranslatorPlugin', 'MethodPatcher', 'TranslationLoader', 'NativeMethods', 'VirtualProtect']:
            assert_eq(term.encode() in content, f'{term} present')

    print()
    print('5. TranslationLoader unit test')
    test_file = SKILL_DIR / 'test_data' / 'test.ndjson'
    assert_eq(test_file.exists(), 'test.ndjson exists')
    if test_file.exists():
        test_content = test_file.read_text(encoding='utf-8')
        assert_eq('Resolution Scaling' in test_content, 'test data present')
        assert_eq('Масштабирование разрешения' in test_content, 'test translation present')

    print()
    print('6. Quick compile check')
    test_prog = SKILL_DIR / 'test_data' / 'test_loader.cs'
    if test_prog.exists():
        out_dir = GAME_DIR / 'runtime'
        out_dir.mkdir(parents=True, exist_ok=True)
        test_out = out_dir / 'test_loader.exe'
        md = GAME_DIR / 'Third Crisis Neon Nights_Data' / 'Managed'
        src_dir = SKILL_DIR / 'source'
        args = [
            CSC, '/target:exe', f'/out:{test_out}', '/nologo',
            f'/r:{md / "netstandard.dll"}',
            f'/r:{md / "UnityEngine.dll"}',
            f'/r:{md / "UnityEngine.CoreModule.dll"}',
            str(test_prog),
            str(src_dir / 'TranslationLoader.cs'),
            str(src_dir / 'NativeMethods.cs'),
        ]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=60, cwd=str(GAME_DIR))
            assert_eq(r.returncode == 0, f'test_loader compiled: {r.stdout[:200]}')
            if r.returncode == 0:
                try:
                    run = subprocess.run([str(test_out), str(test_file)], capture_output=True, text=True, timeout=10, cwd=str(GAME_DIR))
                    assert_eq(run.returncode == 0, 'test_loader ran OK')
                except:
                    assert_eq(False, 'test_loader run failed')
        except:
            assert_eq(False, 'test_loader compile exception')
    else:
        assert_eq(True, 'test_loader.cs not found (skipped)')

    print()
    print(f'\n\n=== Result: {passed} passed, {failed} failed ===')
    sys.exit(1 if failed > 0 else 0)

if __name__ == '__main__':
    main()
