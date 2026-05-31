#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

static void DebugLog(const char* msg)
{
    HANDLE h = CreateFileA("C:\\temp\\version_proxy.log", FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        DWORD written;
        WriteFile(h, msg, (DWORD)strlen(msg), &written, NULL);
        WriteFile(h, "\r\n", 2, &written, NULL);
        CloseHandle(h);
    }
}

// Linker export directives: map internal Proxy_* names to original version.dll exports
#pragma comment(linker, "/export:GetFileVersionInfoA=Proxy_GetFileVersionInfoA")
#pragma comment(linker, "/export:GetFileVersionInfoByHandle=Proxy_GetFileVersionInfoByHandle")
#pragma comment(linker, "/export:GetFileVersionInfoExA=Proxy_GetFileVersionInfoExA")
#pragma comment(linker, "/export:GetFileVersionInfoExW=Proxy_GetFileVersionInfoExW")
#pragma comment(linker, "/export:GetFileVersionInfoSizeA=Proxy_GetFileVersionInfoSizeA")
#pragma comment(linker, "/export:GetFileVersionInfoSizeExA=Proxy_GetFileVersionInfoSizeExA")
#pragma comment(linker, "/export:GetFileVersionInfoSizeExW=Proxy_GetFileVersionInfoSizeExW")
#pragma comment(linker, "/export:GetFileVersionInfoSizeW=Proxy_GetFileVersionInfoSizeW")
#pragma comment(linker, "/export:GetFileVersionInfoW=Proxy_GetFileVersionInfoW")
#pragma comment(linker, "/export:VerFindFileA=Proxy_VerFindFileA")
#pragma comment(linker, "/export:VerFindFileW=Proxy_VerFindFileW")
#pragma comment(linker, "/export:VerInstallFileA=Proxy_VerInstallFileA")
#pragma comment(linker, "/export:VerInstallFileW=Proxy_VerInstallFileW")
#pragma comment(linker, "/export:VerLanguageNameA=Proxy_VerLanguageNameA")
#pragma comment(linker, "/export:VerLanguageNameW=Proxy_VerLanguageNameW")
#pragma comment(linker, "/export:VerQueryValueA=Proxy_VerQueryValueA")
#pragma comment(linker, "/export:VerQueryValueW=Proxy_VerQueryValueW")

// Mono API typedefs
typedef void* (*mono_get_root_domain_t)(void);
typedef void* (*mono_domain_assembly_open_t)(void*, const char*);
typedef void* (*mono_assembly_get_image_t)(void*);
typedef void* (*mono_class_from_name_t)(void*, const char*, const char*);
typedef void* (*mono_class_get_method_from_name_t)(void*, const char*, int);
typedef void* (*mono_runtime_invoke_t)(void*, void*, void**, void**);

static volatile LONG g_runtimeLoaded = 0;
static HMODULE g_realVersion = NULL;

static void EnsureRealVersion(void)
{
    if (!g_realVersion)
    {
        wchar_t sysPath[MAX_PATH];
        GetSystemDirectoryW(sysPath, MAX_PATH);
        wcscat_s(sysPath, MAX_PATH, L"\\version.dll");
        g_realVersion = LoadLibraryW(sysPath);
    }
}

static int BootstrapTranslator(void)
{
    DebugLog("BootstrapTranslator: start");

    HMODULE hMono = LoadLibraryW(L"MonoBleedingEdge\\EmbedRuntime\\mono-2.0-bdwgc.dll");
    if (!hMono) { DebugLog("BootstrapTranslator: FAIL LoadLibrary mono"); return 0; }
    DebugLog("BootstrapTranslator: mono loaded");

    mono_get_root_domain_t mono_get_root_domain =
        (mono_get_root_domain_t)GetProcAddress(hMono, "mono_get_root_domain");
    mono_domain_assembly_open_t mono_domain_assembly_open =
        (mono_domain_assembly_open_t)GetProcAddress(hMono, "mono_domain_assembly_open");
    mono_assembly_get_image_t mono_assembly_get_image =
        (mono_assembly_get_image_t)GetProcAddress(hMono, "mono_assembly_get_image");
    mono_class_from_name_t mono_class_from_name =
        (mono_class_from_name_t)GetProcAddress(hMono, "mono_class_from_name");
    mono_class_get_method_from_name_t mono_class_get_method_from_name =
        (mono_class_get_method_from_name_t)GetProcAddress(hMono, "mono_class_get_method_from_name");
    mono_runtime_invoke_t mono_runtime_invoke =
        (mono_runtime_invoke_t)GetProcAddress(hMono, "mono_runtime_invoke");

    if (!mono_get_root_domain || !mono_domain_assembly_open || !mono_assembly_get_image ||
        !mono_class_from_name || !mono_class_get_method_from_name || !mono_runtime_invoke)
    { DebugLog("BootstrapTranslator: FAIL GetProcAddress mono API"); return 0; }
    DebugLog("BootstrapTranslator: mono API resolved");

    void* domain = mono_get_root_domain();
    if (!domain) { DebugLog("BootstrapTranslator: FAIL mono_get_root_domain"); return 0; }
    DebugLog("BootstrapTranslator: root domain OK");

    wchar_t dllPath[MAX_PATH];
    GetCurrentDirectoryW(MAX_PATH, dllPath);
    wcscat_s(dllPath, MAX_PATH, L"\\Third Crisis Neon Nights_Data\\Managed\\NeonTranslatorRuntime.dll");

    char dllPathUtf8[MAX_PATH * 2];
    WideCharToMultiByte(CP_UTF8, 0, dllPath, -1, dllPathUtf8, (int)sizeof(dllPathUtf8), NULL, NULL);
    DebugLog(dllPathUtf8);

    void* assembly = mono_domain_assembly_open(domain, dllPathUtf8);
    if (!assembly) { DebugLog("BootstrapTranslator: FAIL mono_domain_assembly_open"); return 0; }
    DebugLog("BootstrapTranslator: assembly loaded OK");

    void* image = mono_assembly_get_image(assembly);
    if (!image) { DebugLog("BootstrapTranslator: FAIL mono_assembly_get_image"); return 0; }

    void* klass = mono_class_from_name(image, "NeonTranslator", "TranslatorPlugin");
    if (!klass) { DebugLog("BootstrapTranslator: FAIL mono_class_from_name"); return 0; }
    DebugLog("BootstrapTranslator: class found");

    void* method = mono_class_get_method_from_name(klass, "Initialize", 0);
    if (!method) { DebugLog("BootstrapTranslator: FAIL mono_class_get_method_from_name"); return 0; }
    DebugLog("BootstrapTranslator: method found, invoking...");

    mono_runtime_invoke(method, NULL, NULL, NULL);
    DebugLog("BootstrapTranslator: SUCCESS");
    return 1;
}

static void TryBootstrap(void)
{
    if (g_runtimeLoaded) { DebugLog("TryBootstrap: already loaded, skip"); return; }
    DebugLog("TryBootstrap: first call, starting bootstrap");
    if (!g_realVersion) { DebugLog("TryBootstrap: EnsureRealVersion"); EnsureRealVersion(); }
    if (!g_realVersion) { DebugLog("TryBootstrap: FAIL g_realVersion null"); return; }
    if (BootstrapTranslator()) {
        g_runtimeLoaded = 1;
        DebugLog("TryBootstrap: SUCCESS, translator loaded");
    } else {
        DebugLog("TryBootstrap: bootstrap failed, will retry");
    }
}

// --- 17 version.dll exports, each forwarding to real C:\Windows\System32\version.dll ---

BOOL WINAPI Proxy_GetFileVersionInfoA(LPCSTR lptstrFilename, DWORD dwHandle, DWORD dwLen, LPVOID lpData)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoA"); if (fp) return ((BOOL (WINAPI*)(LPCSTR,DWORD,DWORD,LPVOID))fp)(lptstrFilename, dwHandle, dwLen, lpData); return 0; }

BOOL WINAPI Proxy_GetFileVersionInfoByHandle(HANDLE hFile, DWORD dwLen, LPVOID lpData)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoByHandle"); if (fp) return ((BOOL (WINAPI*)(HANDLE,DWORD,LPVOID))fp)(hFile, dwLen, lpData); return 0; }

BOOL WINAPI Proxy_GetFileVersionInfoExA(DWORD dwFlags, LPCSTR lptstrFilename, DWORD dwHandle, DWORD dwLen, LPVOID lpData)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoExA"); if (fp) return ((BOOL (WINAPI*)(DWORD,LPCSTR,DWORD,DWORD,LPVOID))fp)(dwFlags, lptstrFilename, dwHandle, dwLen, lpData); return 0; }

BOOL WINAPI Proxy_GetFileVersionInfoExW(DWORD dwFlags, LPCWSTR lptstrFilename, DWORD dwHandle, DWORD dwLen, LPVOID lpData)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoExW"); if (fp) return ((BOOL (WINAPI*)(DWORD,LPCWSTR,DWORD,DWORD,LPVOID))fp)(dwFlags, lptstrFilename, dwHandle, dwLen, lpData); return 0; }

DWORD WINAPI Proxy_GetFileVersionInfoSizeA(LPCSTR lptstrFilename, LPDWORD lpdwHandle)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoSizeA"); if (fp) return ((DWORD (WINAPI*)(LPCSTR,LPDWORD))fp)(lptstrFilename, lpdwHandle); return 0; }

DWORD WINAPI Proxy_GetFileVersionInfoSizeExA(DWORD dwFlags, LPCSTR lptstrFilename, LPDWORD lpdwHandle)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoSizeExA"); if (fp) return ((DWORD (WINAPI*)(DWORD,LPCSTR,LPDWORD))fp)(dwFlags, lptstrFilename, lpdwHandle); return 0; }

DWORD WINAPI Proxy_GetFileVersionInfoSizeExW(DWORD dwFlags, LPCWSTR lptstrFilename, LPDWORD lpdwHandle)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoSizeExW"); if (fp) return ((DWORD (WINAPI*)(DWORD,LPCWSTR,LPDWORD))fp)(dwFlags, lptstrFilename, lpdwHandle); return 0; }

DWORD WINAPI Proxy_GetFileVersionInfoSizeW(LPCWSTR lptstrFilename, LPDWORD lpdwHandle)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoSizeW"); if (fp) return ((DWORD (WINAPI*)(LPCWSTR,LPDWORD))fp)(lptstrFilename, lpdwHandle); return 0; }

BOOL WINAPI Proxy_GetFileVersionInfoW(LPCWSTR lptstrFilename, DWORD dwHandle, DWORD dwLen, LPVOID lpData)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "GetFileVersionInfoW"); if (fp) return ((BOOL (WINAPI*)(LPCWSTR,DWORD,DWORD,LPVOID))fp)(lptstrFilename, dwHandle, dwLen, lpData); return 0; }

DWORD WINAPI Proxy_VerFindFileA(DWORD dwFlags, LPCSTR szFileName, LPCSTR szWinDir, LPCSTR szAppDir, LPSTR szCurDir, UINT* lpuCurDirLen, LPSTR szDestDir, UINT* lpuDestDirLen)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "VerFindFileA"); if (fp) return ((DWORD (WINAPI*)(DWORD,LPCSTR,LPCSTR,LPCSTR,LPSTR,UINT*,LPSTR,UINT*))fp)(dwFlags, szFileName, szWinDir, szAppDir, szCurDir, lpuCurDirLen, szDestDir, lpuDestDirLen); return 0; }

DWORD WINAPI Proxy_VerFindFileW(DWORD dwFlags, LPCWSTR szFileName, LPCWSTR szWinDir, LPCWSTR szAppDir, LPWSTR szCurDir, UINT* lpuCurDirLen, LPWSTR szDestDir, UINT* lpuDestDirLen)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "VerFindFileW"); if (fp) return ((DWORD (WINAPI*)(DWORD,LPCWSTR,LPCWSTR,LPCWSTR,LPWSTR,UINT*,LPWSTR,UINT*))fp)(dwFlags, szFileName, szWinDir, szAppDir, szCurDir, lpuCurDirLen, szDestDir, lpuDestDirLen); return 0; }

DWORD WINAPI Proxy_VerInstallFileA(DWORD dwFlags, LPCSTR szSrcFileName, LPCSTR szDestFileName, LPCSTR szSrcDir, LPCSTR szDestDir, LPCSTR szCurDir, LPSTR szTmpFile, UINT* lpuTmpFileLen)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "VerInstallFileA"); if (fp) return ((DWORD (WINAPI*)(DWORD,LPCSTR,LPCSTR,LPCSTR,LPCSTR,LPCSTR,LPSTR,UINT*))fp)(dwFlags, szSrcFileName, szDestFileName, szSrcDir, szDestDir, szCurDir, szTmpFile, lpuTmpFileLen); return 0; }

DWORD WINAPI Proxy_VerInstallFileW(DWORD dwFlags, LPCWSTR szSrcFileName, LPCWSTR szDestFileName, LPCWSTR szSrcDir, LPCWSTR szDestDir, LPCWSTR szCurDir, LPWSTR szTmpFile, UINT* lpuTmpFileLen)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "VerInstallFileW"); if (fp) return ((DWORD (WINAPI*)(DWORD,LPCWSTR,LPCWSTR,LPCWSTR,LPCWSTR,LPCWSTR,LPWSTR,UINT*))fp)(dwFlags, szSrcFileName, szDestFileName, szSrcDir, szDestDir, szCurDir, szTmpFile, lpuTmpFileLen); return 0; }

DWORD WINAPI Proxy_VerLanguageNameA(DWORD wLang, LPSTR szLang, DWORD cchLang)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "VerLanguageNameA"); if (fp) return ((DWORD (WINAPI*)(DWORD,LPSTR,DWORD))fp)(wLang, szLang, cchLang); return 0; }

DWORD WINAPI Proxy_VerLanguageNameW(DWORD wLang, LPWSTR szLang, DWORD cchLang)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "VerLanguageNameW"); if (fp) return ((DWORD (WINAPI*)(DWORD,LPWSTR,DWORD))fp)(wLang, szLang, cchLang); return 0; }

BOOL WINAPI Proxy_VerQueryValueA(LPCVOID pBlock, LPCSTR lpSubBlock, LPVOID* lplpBuffer, PUINT puLen)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "VerQueryValueA"); if (fp) return ((BOOL (WINAPI*)(LPCVOID,LPCSTR,LPVOID*,PUINT))fp)(pBlock, lpSubBlock, lplpBuffer, puLen); return 0; }

BOOL WINAPI Proxy_VerQueryValueW(LPCVOID pBlock, LPCWSTR lpSubBlock, LPVOID* lplpBuffer, PUINT puLen)
{ TryBootstrap(); FARPROC fp = GetProcAddress(g_realVersion, "VerQueryValueW"); if (fp) return ((BOOL (WINAPI*)(LPCVOID,LPCWSTR,LPVOID*,PUINT))fp)(pBlock, lpSubBlock, lplpBuffer, puLen); return 0; }

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    (void)hModule;
    (void)lpReserved;
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        DebugLog("DllMain: DLL_PROCESS_ATTACH");
        EnsureRealVersion();
        DebugLog("DllMain: EnsureRealVersion done");
    }
    return TRUE;
}
