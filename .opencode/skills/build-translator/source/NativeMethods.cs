using System;
using System.Runtime.InteropServices;

namespace NeonTranslator
{
    internal static class NativeMethods
    {
        [DllImport("gdi32.dll", SetLastError = true)]
        public static extern IntPtr AddFontMemResourceEx(
            byte[] pbFont,
            uint cbFont,
            IntPtr pdv,
            out uint pcFonts
        );
    }
}
