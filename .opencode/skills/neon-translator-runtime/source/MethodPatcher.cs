using System;
using System.Reflection;
using System.Runtime.InteropServices;

namespace NeonTranslator
{
    internal static class MethodPatcher
    {
        private static IntPtr _trampolineTmpro;
        private static IntPtr _trampolineUiText;
        private static byte[] _origCodeTmpro;
        private static byte[] _origCodeUiText;

        private static readonly int JMP_SIZE = 12;

        private static void Log(string msg)
        {
            try { System.IO.File.AppendAllText(
                System.IO.Path.Combine(
                    System.IO.Path.GetDirectoryName(
                        System.Reflection.Assembly.GetExecutingAssembly().Location),
                    "NeonTranslator.log"),
                msg + "\n"); } catch { }
        }

        private static IntPtr AllocTrampoline(byte[] origBytes, IntPtr targetAfterJmp)
        {
            int trampSize = origBytes.Length + JMP_SIZE;
            IntPtr tramp = NativeMethods.VirtualAlloc(
                IntPtr.Zero, (UIntPtr)trampSize,
                NativeMethods.MEM_COMMIT | NativeMethods.MEM_RESERVE,
                NativeMethods.PAGE_EXECUTE_READWRITE);
            if (tramp == IntPtr.Zero) return IntPtr.Zero;

            Marshal.Copy(origBytes, 0, tramp, origBytes.Length);
            WriteJmpCode(tramp + origBytes.Length, targetAfterJmp);
            return tramp;
        }

        private static void WriteJmpCode(IntPtr target, IntPtr destination)
        {
            byte[] jmp = new byte[]
            {
                0x48, 0xB8,
                (byte)((long)destination >> 0),
                (byte)((long)destination >> 8),
                (byte)((long)destination >> 16),
                (byte)((long)destination >> 24),
                (byte)((long)destination >> 32),
                (byte)((long)destination >> 40),
                (byte)((long)destination >> 48),
                (byte)((long)destination >> 56),
                0xFF, 0xE0
            };
            Marshal.Copy(jmp, 0, target, JMP_SIZE);
        }

        private static IntPtr InstallPatch(IntPtr target, IntPtr hook)
        {
            byte[] origCode = new byte[JMP_SIZE];
            Marshal.Copy(target, origCode, 0, JMP_SIZE);

            IntPtr trampoline = AllocTrampoline(origCode, target + JMP_SIZE);
            if (trampoline == IntPtr.Zero) { Log("InstallPatch: AllocTrampoline FAILED"); return IntPtr.Zero; }
            Log("InstallPatch: trampoline at " + trampoline.ToString("X8"));

            uint oldProtect;
            if (!NativeMethods.VirtualProtect(target, (UIntPtr)JMP_SIZE,
                NativeMethods.PAGE_EXECUTE_READWRITE, out oldProtect))
            { Log("InstallPatch: VirtualProtect FAILED"); return IntPtr.Zero; }

            WriteJmpCode(target, hook);

            NativeMethods.VirtualProtect(target, (UIntPtr)JMP_SIZE, oldProtect, out oldProtect);
            Log("InstallPatch: DONE target=" + target.ToString("X8") + " hook=" + hook.ToString("X8"));

            return trampoline;
        }

        public static void Patch()
        {
            Log("Patch(TMP_Text): starting");
            var tmproAssembly = FindTMProAssembly();
            if (tmproAssembly == null) { Log("Patch(TMP_Text): FindTMProAssembly NULL"); return; }

            var tmpTextField = tmproAssembly.GetType("TMPro.TMP_Text");
            if (tmpTextField == null) { Log("Patch(TMP_Text): GetType TMP_Text NULL"); return; }

            var setTextMethod = tmpTextField.GetMethod("set_text",
                BindingFlags.Public | BindingFlags.Instance);
            if (setTextMethod == null) { Log("Patch(TMP_Text): GetMethod set_text NULL"); return; }

            IntPtr target = setTextMethod.MethodHandle.GetFunctionPointer();
            Log("Patch(TMP_Text): target=" + target.ToString("X8"));

            IntPtr hook = Marshal.GetFunctionPointerForDelegate(
                new SetTextDelegate(HookTmpro));
            Log("Patch(TMP_Text): hook=" + hook.ToString("X8"));

            _trampolineTmpro = InstallPatch(target, hook);
        }

        public static void PatchUIText()
        {
            Log("PatchUI(Text): starting");
            var uiAssembly = FindUIAssembly();
            if (uiAssembly == null) { Log("PatchUI(Text): FindUIAssembly NULL"); return; }

            var textType = uiAssembly.GetType("UnityEngine.UI.Text");
            if (textType == null) { Log("PatchUI(Text): GetType Text NULL"); return; }

            var setTextMethod = textType.GetMethod("set_text",
                BindingFlags.Public | BindingFlags.Instance);
            if (setTextMethod == null) { Log("PatchUI(Text): GetMethod set_text NULL"); return; }

            IntPtr target = setTextMethod.MethodHandle.GetFunctionPointer();
            Log("PatchUI(Text): target=" + target.ToString("X8"));

            IntPtr hook = Marshal.GetFunctionPointerForDelegate(
                new SetTextDelegate(HookUiText));
            Log("PatchUI(Text): hook=" + hook.ToString("X8"));

            _trampolineUiText = InstallPatch(target, hook);
        }

        private static Assembly FindTMProAssembly()
        {
            Assembly[] asms = AppDomain.CurrentDomain.GetAssemblies();
            for (int i = 0; i < asms.Length; i++)
            {
                string name = asms[i].GetName().Name;
                if (name == "Unity.TextMeshPro" ||
                    name == "UnityEngine.UI" ||
                    name.StartsWith("Unity.TextMeshPro"))
                    return asms[i];
            }
            return null;
        }

        private static Assembly FindUIAssembly()
        {
            Assembly[] asms = AppDomain.CurrentDomain.GetAssemblies();
            for (int i = 0; i < asms.Length; i++)
            {
                string name = asms[i].GetName().Name;
                if (name == "UnityEngine.UI")
                    return asms[i];
            }
            return null;
        }

        private delegate void SetTextDelegate(IntPtr instance, string value);

        private static int _hookCallCount = 0;

        private static void HookTmpro(IntPtr instance, string value)
        {
            _hookCallCount++;
            if (_hookCallCount <= 20)
                Log("HookTmpro #" + _hookCallCount + " value='" + (value ?? "null") + "'");

            if (!string.IsNullOrEmpty(value))
            {
                string translated = TranslatorPlugin.Translate(value);
                if (translated != null) value = translated;
            }

            var orig = Marshal.GetDelegateForFunctionPointer(
                _trampolineTmpro, typeof(SetTextDelegate)) as SetTextDelegate;
            if (orig != null) orig(instance, value);
        }

        private static int _hookUICallCount = 0;

        private static void HookUiText(IntPtr instance, string value)
        {
            _hookUICallCount++;
            if (_hookUICallCount <= 20)
                Log("HookUiText #" + _hookUICallCount + " value='" + (value ?? "null") + "'");

            if (!string.IsNullOrEmpty(value))
            {
                string translated = TranslatorPlugin.Translate(value);
                if (translated != null) value = translated;
            }

            var orig = Marshal.GetDelegateForFunctionPointer(
                _trampolineUiText, typeof(SetTextDelegate)) as SetTextDelegate;
            if (orig != null) orig(instance, value);
        }
    }
}
