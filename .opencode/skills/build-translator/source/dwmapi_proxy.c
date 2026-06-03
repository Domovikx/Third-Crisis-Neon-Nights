#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

// Log to C:\temp\dwmapi_proxy.log
static void DebugLog(const char* msg)
{
    HANDLE h = CreateFileA("C:\\temp\\dwmapi_proxy.log", FILE_APPEND_DATA, FILE_SHARE_READ, NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        DWORD written;
        WriteFile(h, msg, (DWORD)strlen(msg), &written, NULL);
        WriteFile(h, "\r\n", 2, &written, NULL);
        CloseHandle(h);
    }
}

// Intercept these two (imported by UnityPlayer.dll)
#pragma comment(linker, "/export:DwmSetWindowAttribute=Proxy_DwmSetWindowAttribute")
#pragma comment(linker, "/export:DwmGetWindowAttribute=Proxy_DwmGetWindowAttribute")

// Forward ALL other dwmapi exports to dwmapi_real.dll
#pragma comment(linker, "/export:DllCanUnloadNow=dwmapi_real.DllCanUnloadNow")
#pragma comment(linker, "/export:DllGetClassObject=dwmapi_real.DllGetClassObject")
#pragma comment(linker, "/export:DwmAttachMilContent=dwmapi_real.DwmAttachMilContent")
#pragma comment(linker, "/export:DwmDefWindowProc=dwmapi_real.DwmDefWindowProc")
#pragma comment(linker, "/export:DwmDetachMilContent=dwmapi_real.DwmDetachMilContent")
#pragma comment(linker, "/export:DwmEnableBlurBehindWindow=dwmapi_real.DwmEnableBlurBehindWindow")
#pragma comment(linker, "/export:DwmEnableComposition=dwmapi_real.DwmEnableComposition")
#pragma comment(linker, "/export:DwmEnableMMCSS=dwmapi_real.DwmEnableMMCSS")
#pragma comment(linker, "/export:DwmExtendFrameIntoClientArea=dwmapi_real.DwmExtendFrameIntoClientArea")
#pragma comment(linker, "/export:DwmFlush=dwmapi_real.DwmFlush")
#pragma comment(linker, "/export:DwmGetColorizationColor=dwmapi_real.DwmGetColorizationColor")
#pragma comment(linker, "/export:DwmGetCompositionTimingInfo=dwmapi_real.DwmGetCompositionTimingInfo")
#pragma comment(linker, "/export:DwmGetGraphicsStreamClient=dwmapi_real.DwmGetGraphicsStreamClient")
#pragma comment(linker, "/export:DwmGetGraphicsStreamTransformHint=dwmapi_real.DwmGetGraphicsStreamTransformHint")
#pragma comment(linker, "/export:DwmGetTransportAttributes=dwmapi_real.DwmGetTransportAttributes")
#pragma comment(linker, "/export:DwmGetUnmetTabRequirements=dwmapi_real.DwmGetUnmetTabRequirements")
#pragma comment(linker, "/export:DwmInvalidateIconicBitmaps=dwmapi_real.DwmInvalidateIconicBitmaps")
#pragma comment(linker, "/export:DwmIsCompositionEnabled=dwmapi_real.DwmIsCompositionEnabled")
#pragma comment(linker, "/export:DwmModifyPreviousDxFrameDuration=dwmapi_real.DwmModifyPreviousDxFrameDuration")
#pragma comment(linker, "/export:DwmQueryThumbnailSourceSize=dwmapi_real.DwmQueryThumbnailSourceSize")
#pragma comment(linker, "/export:DwmRegisterThumbnail=dwmapi_real.DwmRegisterThumbnail")
#pragma comment(linker, "/export:DwmRenderGesture=dwmapi_real.DwmRenderGesture")
#pragma comment(linker, "/export:DwmSetDxFrameDuration=dwmapi_real.DwmSetDxFrameDuration")
#pragma comment(linker, "/export:DwmSetIconicLivePreviewBitmap=dwmapi_real.DwmSetIconicLivePreviewBitmap")
#pragma comment(linker, "/export:DwmSetIconicThumbnail=dwmapi_real.DwmSetIconicThumbnail")
#pragma comment(linker, "/export:DwmSetPresentParameters=dwmapi_real.DwmSetPresentParameters")
#pragma comment(linker, "/export:DwmShowContact=dwmapi_real.DwmShowContact")
#pragma comment(linker, "/export:DwmTetherContact=dwmapi_real.DwmTetherContact")
#pragma comment(linker, "/export:DwmTetherTextContact=dwmapi_real.DwmTetherTextContact")
#pragma comment(linker, "/export:DwmTransitionOwnedWindow=dwmapi_real.DwmTransitionOwnedWindow")
#pragma comment(linker, "/export:DwmUnregisterThumbnail=dwmapi_real.DwmUnregisterThumbnail")
#pragma comment(linker, "/export:DwmUpdateThumbnailProperties=dwmapi_real.DwmUpdateThumbnailProperties")

// Mono API
typedef void* (*mono_get_root_domain_t)(void);
typedef void* (*mono_domain_assembly_open_t)(void*, const char*);
typedef void* (*mono_assembly_get_image_t)(void*);
typedef void* (*mono_class_from_name_t)(void*, const char*, const char*);
typedef void* (*mono_class_get_method_from_name_t)(void*, const char*, int);
typedef void* (*mono_runtime_invoke_t)(void*, void*, void**, void**);

static volatile LONG g_initialized = 0;

static void BootstrapTranslator(void)
{
    HMODULE hMono = LoadLibraryW(L"MonoBleedingEdge\\EmbedRuntime\\mono-2.0-bdwgc.dll");
    if (!hMono) { DebugLog("FAIL: LoadLibrary mono-2.0-bdwgc.dll"); return; }
    DebugLog("OK: mono loaded");

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
    { DebugLog("FAIL: GetProcAddress mono API"); return; }
    DebugLog("OK: mono API resolved");

    void* domain = mono_get_root_domain();
    if (!domain) { DebugLog("FAIL: mono_get_root_domain = NULL"); return; }
    DebugLog("OK: root domain obtained");

    wchar_t dllPath[MAX_PATH];
    GetCurrentDirectoryW(MAX_PATH, dllPath);
    wcscat_s(dllPath, MAX_PATH, L"\\Third Crisis Neon Nights_Data\\Managed\\NeonTranslatorRuntime.dll");

    char dllPathUtf8[MAX_PATH * 2];
    WideCharToMultiByte(CP_UTF8, 0, dllPath, -1, dllPathUtf8, (int)sizeof(dllPathUtf8), NULL, NULL);
    DebugLog(dllPathUtf8);

    void* assembly = mono_domain_assembly_open(domain, dllPathUtf8);
    if (!assembly) { DebugLog("FAIL: mono_domain_assembly_open"); return; }
    DebugLog("OK: assembly opened");

    void* image = mono_assembly_get_image(assembly);
    if (!image) { DebugLog("FAIL: mono_assembly_get_image"); return; }
    DebugLog("OK: image obtained");

    void* klass = mono_class_from_name(image, "NeonTranslator", "TranslatorPlugin");
    if (!klass) { DebugLog("FAIL: mono_class_from_name"); return; }
    DebugLog("OK: class found");

    void* method = mono_class_get_method_from_name(klass, "Initialize", 0);
    if (!method) { DebugLog("FAIL: mono_class_get_method_from_name"); return; }
    DebugLog("OK: Initialize method found, invoking...");

    mono_runtime_invoke(method, NULL, NULL, NULL);
    DebugLog("OK: mono_runtime_invoke returned");
}

// Our two intercepted exports
HRESULT WINAPI Proxy_DwmSetWindowAttribute(HWND hwnd, DWORD dwAttribute, LPCVOID pvAttribute, DWORD cbAttribute)
{
    if (!g_initialized) { g_initialized = 1; BootstrapTranslator(); }
    HMODULE hReal = GetModuleHandleW(L"dwmapi_real");
    FARPROC fp = hReal ? GetProcAddress(hReal, "DwmSetWindowAttribute") : NULL;
    if (fp) return ((HRESULT (WINAPI*)(HWND,DWORD,LPCVOID,DWORD))fp)(hwnd, dwAttribute, pvAttribute, cbAttribute);
    return 0;
}

HRESULT WINAPI Proxy_DwmGetWindowAttribute(HWND hwnd, DWORD dwAttribute, LPVOID pvAttribute, DWORD cbAttribute)
{
    if (!g_initialized) { g_initialized = 1; BootstrapTranslator(); }
    HMODULE hReal = GetModuleHandleW(L"dwmapi_real");
    FARPROC fp = hReal ? GetProcAddress(hReal, "DwmGetWindowAttribute") : NULL;
    if (fp) return ((HRESULT (WINAPI*)(HWND,DWORD,LPVOID,DWORD))fp)(hwnd, dwAttribute, pvAttribute, cbAttribute);
    return 0;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    (void)hModule;
    (void)lpReserved;
    if (ul_reason_for_call == DLL_PROCESS_ATTACH)
        LoadLibraryW(L"dwmapi_real");
    return TRUE;
}
