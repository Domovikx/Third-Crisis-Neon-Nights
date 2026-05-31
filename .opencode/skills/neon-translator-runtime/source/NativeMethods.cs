using System;
using System.Runtime.InteropServices;

namespace NeonTranslator
{
    internal static class NativeMethods
    {
        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern bool VirtualProtect(
            IntPtr lpAddress,
            UIntPtr dwSize,
            uint flNewProtect,
            out uint lpflOldProtect
        );

        [DllImport("kernel32.dll", SetLastError = true)]
        public static extern IntPtr VirtualAlloc(
            IntPtr lpAddress,
            UIntPtr dwSize,
            uint flAllocationType,
            uint flProtect
        );

        [DllImport("kernel32.dll")]
        public static extern IntPtr GetModuleHandle(string lpModuleName);

        [DllImport("kernel32.dll")]
        public static extern IntPtr GetProcAddress(IntPtr hModule, string lpProcName);

        public const uint PAGE_EXECUTE_READWRITE = 0x40;
        public const uint MEM_COMMIT = 0x1000;
        public const uint MEM_RESERVE = 0x2000;
    }
}
