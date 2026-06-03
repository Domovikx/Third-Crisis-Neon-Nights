using System;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;

namespace NeonTranslator
{
    internal static class MethodPatcher
    {
        private static IntPtr _trampolineTmpro;
        private static IntPtr _trampolineUiText;
        private static readonly int JMP_SIZE = 12;

        // MonoString layout detection
        private static int _lengthOffset = -1;
        private static int _charsOffset = -1;

        private static void Log(string msg)
        {
            try { System.IO.File.AppendAllText(
                System.IO.Path.Combine(
                    System.IO.Path.GetDirectoryName(
                        System.Reflection.Assembly.GetExecutingAssembly().Location),
                    "NeonTranslator.log"),
                msg + "\n"); } catch { }
        }

        private static string ReadMonoString(IntPtr ptr)
        {
            if (ptr == IntPtr.Zero) return null;

            // Try to detect MonoString layout: MonoObject{vtable(8), sync(8)} + length(4) + chars
            // x64: vtable(8) + sync(8) = 16, then length at +16, chars at +20
            // If sync is 4 bytes: vtable(8) + sync(4) = 12, then length at +12, chars at +16
            int[] tryOffsets = { 16, 12, 20, 8 };
            int[] tryChars = { 20, 16, 24, 12 };

            if (_lengthOffset > 0)
            {
                int len = Marshal.ReadInt32(ptr, _lengthOffset);
                if (len > 0 && len < 65536)
                {
                    byte[] buf = new byte[len * 2];
                    Marshal.Copy(ptr + _charsOffset, buf, 0, buf.Length);
                    return Encoding.Unicode.GetString(buf);
                }
                return null;
            }

            // Detect by trying each offset
            for (int i = 0; i < tryOffsets.Length; i++)
            {
                int len = Marshal.ReadInt32(ptr, tryOffsets[i]);
                if (len > 0 && len < 65536)
                {
                    byte[] buf = new byte[len * 2];
                    try
                    {
                        Marshal.Copy(ptr + tryChars[i], buf, 0, buf.Length);
                        string result = Encoding.Unicode.GetString(buf);
                        if (!string.IsNullOrEmpty(result))
                        {
                            _lengthOffset = tryOffsets[i];
                            _charsOffset = tryChars[i];
                            Log("ReadMonoString: detected layout len@+" + _lengthOffset
                                + " chars@+" + _charsOffset + " text='" + result + "'");
                            return result;
                        }
                    }
                    catch { }
                }
            }
            Log("ReadMonoString: FAILED to detect layout ptr=" + ptr.ToString("X8"));
            return null;
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

            // Use IntPtr,IntPtr to avoid string marshaling issues
            var hookDel = new SetTextRawDelegate(HookTmproRaw);
            IntPtr hook = Marshal.GetFunctionPointerForDelegate(hookDel);
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

            var hookDel = new SetTextRawDelegate(HookUiTextRaw);
            IntPtr hook = Marshal.GetFunctionPointerForDelegate(hookDel);
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

        // Raw IntPtr,IntPtr delegate to avoid string marshaling issues
        private delegate void SetTextRawDelegate(IntPtr instance, IntPtr valuePtr);

        private static int _hookCallCount = 0;

        private static void HookTmproRaw(IntPtr instance, IntPtr valuePtr)
        {
            _hookCallCount++;
            if (_hookCallCount <= 20)
            {
                string val = ReadMonoString(valuePtr);
                Log("HookTMP #" + _hookCallCount + " instance=" + instance.ToString("X8")
                    + " value='" + (val ?? "null") + "'");
            }

            // Call original method (passes through the original MonoString pointer)
            var orig = Marshal.GetDelegateForFunctionPointer(
                _trampolineTmpro, typeof(SetTextRawDelegate)) as SetTextRawDelegate;
            if (orig != null) orig(instance, valuePtr);

            // TODO: After original call, set m_text via reflection on the component
            // Need a way to get Component from IntPtr instance
        }

        private static int _hookUICallCount = 0;

        private static void HookUiTextRaw(IntPtr instance, IntPtr valuePtr)
        {
            _hookUICallCount++;
            if (_hookUICallCount <= 20)
            {
                string val = ReadMonoString(valuePtr);
                Log("HookUI #" + _hookUICallCount + " instance=" + instance.ToString("X8")
                    + " value='" + (val ?? "null") + "'");
            }

            var orig = Marshal.GetDelegateForFunctionPointer(
                _trampolineUiText, typeof(SetTextRawDelegate)) as SetTextRawDelegate;
            if (orig != null) orig(instance, valuePtr);
        }
    }
}
