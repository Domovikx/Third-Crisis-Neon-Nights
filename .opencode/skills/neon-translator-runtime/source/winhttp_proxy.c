#define WIN32_LEAN_AND_MEAN
#include <windows.h>

typedef void* HINTERNET;

typedef void* (*mono_get_root_domain_t)(void);
typedef void* (*mono_domain_assembly_open_t)(void*, const char*);
typedef void* (*mono_assembly_get_image_t)(void*);
typedef void* (*mono_class_from_name_t)(void*, const char*, const char*);
typedef void* (*mono_class_get_method_from_name_t)(void*, const char*, int);
typedef void* (*mono_runtime_invoke_t)(void*, void*, void**, void**);

static volatile LONG g_proxyInited = 0;
static volatile LONG g_runtimeLoaded = 0;

static void BootstrapTranslator(void)
{
    HMODULE hMono = LoadLibraryW(L"MonoBleedingEdge\\EmbedRuntime\\mono-2.0-bdwgc.dll");
    if (!hMono) return;

    mono_get_root_domain_t mono_get_root_domain = (mono_get_root_domain_t)GetProcAddress(hMono, "mono_get_root_domain");
    mono_domain_assembly_open_t mono_domain_assembly_open = (mono_domain_assembly_open_t)GetProcAddress(hMono, "mono_domain_assembly_open");
    mono_assembly_get_image_t mono_assembly_get_image = (mono_assembly_get_image_t)GetProcAddress(hMono, "mono_assembly_get_image");
    mono_class_from_name_t mono_class_from_name = (mono_class_from_name_t)GetProcAddress(hMono, "mono_class_from_name");
    mono_class_get_method_from_name_t mono_class_get_method_from_name = (mono_class_get_method_from_name_t)GetProcAddress(hMono, "mono_class_get_method_from_name");
    mono_runtime_invoke_t mono_runtime_invoke = (mono_runtime_invoke_t)GetProcAddress(hMono, "mono_runtime_invoke");

    if (!mono_get_root_domain || !mono_domain_assembly_open || !mono_assembly_get_image ||
        !mono_class_from_name || !mono_class_get_method_from_name || !mono_runtime_invoke)
        return;

    void* domain = mono_get_root_domain();
    if (!domain) return;

    wchar_t dllPath[MAX_PATH];
    GetCurrentDirectoryW(MAX_PATH, dllPath);
    wcscat_s(dllPath, MAX_PATH, L"\\Third Crisis Neon Nights_Data\\Managed\\NeonTranslatorRuntime.dll");

    char dllPathUtf8[MAX_PATH * 2];
    WideCharToMultiByte(CP_UTF8, 0, dllPath, -1, dllPathUtf8, (int)sizeof(dllPathUtf8), NULL, NULL);

    void* assembly = mono_domain_assembly_open(domain, dllPathUtf8);
    if (!assembly) return;

    void* image = mono_assembly_get_image(assembly);
    if (!image) return;

    void* klass = mono_class_from_name(image, "NeonTranslator", "TranslatorPlugin");
    if (!klass) return;

    void* method = mono_class_get_method_from_name(klass, "Initialize", 0);
    if (!method) return;

    mono_runtime_invoke(method, NULL, NULL, NULL);
}

static DWORD WINAPI DelayedBootstrap(LPVOID)
{
    Sleep(5000);
    BootstrapTranslator();
    return 0;
}

static void TriggerBootstrap(void)
{
    if (InterlockedExchange(&g_runtimeLoaded, 1)) return;
    HANDLE h = CreateThread(NULL, 0, DelayedBootstrap, NULL, 0, NULL);
    if (h) CloseHandle(h);
}

// --- Real WinHttp forwarding ---
static HMODULE g_realWinHttp = NULL;

static void EnsureRealWinHttp(void)
{
    if (!g_realWinHttp)
    {
        wchar_t sysPath[MAX_PATH];
        GetSystemDirectoryW(sysPath, MAX_PATH);
        wcscat_s(sysPath, MAX_PATH, L"\\winhttp.dll");
        g_realWinHttp = LoadLibraryW(sysPath);
    }
}

__declspec(dllexport) void* WINAPI WinHttpOpen(
    LPCWSTR pwszUserAgent,
    DWORD dwAccessType,
    LPCWSTR pwszProxyName,
    LPCWSTR pwszProxyBypass,
    DWORD dwFlags)
{
    EnsureRealWinHttp();
    FARPROC real = GetProcAddress(g_realWinHttp, "WinHttpOpen");
    if (real) return ((void* (WINAPI*)(LPCWSTR,DWORD,LPCWSTR,LPCWSTR,DWORD))real)(pwszUserAgent, dwAccessType, pwszProxyName, pwszProxyBypass, dwFlags);
    return NULL;
}

__declspec(dllexport) BOOL WINAPI WinHttpCloseHandle(HINTERNET hInternet)
{
    EnsureRealWinHttp();
    FARPROC real = GetProcAddress(g_realWinHttp, "WinHttpCloseHandle");
    if (real) return ((BOOL (WINAPI*)(HINTERNET))real)(hInternet);
    return FALSE;
}

__declspec(dllexport) BOOL WINAPI WinHttpGetProxyForUrl(
    HINTERNET hSession,
    LPCWSTR lpcwszUrl,
    DWORD dwAutoDetectFlags,
    void* pProxyInfo,
    DWORD* pdwProxyInfoLength)
{
    EnsureRealWinHttp();
    FARPROC real = GetProcAddress(g_realWinHttp, "WinHttpGetProxyForUrl");
    if (real) return ((BOOL (WINAPI*)(HINTERNET,LPCWSTR,DWORD,void*,DWORD*))real)(hSession, lpcwszUrl, dwAutoDetectFlags, pProxyInfo, pdwProxyInfoLength);
    return FALSE;
}

__declspec(dllexport) BOOL WINAPI WinHttpGetIEProxyConfigForCurrentUser(void* pProxyConfig)
{
    EnsureRealWinHttp();
    FARPROC real = GetProcAddress(g_realWinHttp, "WinHttpGetIEProxyConfigForCurrentUser");
    if (real) return ((BOOL (WINAPI*)(void*))real)(pProxyConfig);
    return FALSE;
}

// --- DllMain: trigger bootstrap on first export call ---
static void RetryBootstrap(void)
{
    if (InterlockedCompareExchange(&g_runtimeLoaded, 1, 0)) return;
    BootstrapTranslator();
}

// We hook the first export that gets called to trigger bootstrap
__declspec(dllexport) void* WINAPI WinHttpOpen_Trigger(
    LPCWSTR pwszUserAgent,
    DWORD dwAccessType,
    LPCWSTR pwszProxyName,
    LPCWSTR pwszProxyBypass,
    DWORD dwFlags)
{
    RetryBootstrap();
    return WinHttpOpen(pwszUserAgent, dwAccessType, pwszProxyName, pwszProxyBypass, dwFlags);
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    (void)hModule;
    (void)lpReserved;
    if (ul_reason_for_call == DLL_PROCESS_ATTACH)
    {
        // Try thread-based bootstrap (might work on some Unity versions)
        TriggerBootstrap();
    }
    return TRUE;
}
