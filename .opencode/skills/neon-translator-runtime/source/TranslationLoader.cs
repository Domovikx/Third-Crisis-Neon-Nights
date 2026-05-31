using System;
using System.Collections.Generic;
using System.IO;

namespace NeonTranslator
{
    internal static class TranslationLoader
    {
        private static Dictionary<string, string> _translations;
        private static object _lock = new object();

        public static Dictionary<string, string> Load(string filePath)
        {
            lock (_lock)
            {
                if (_translations != null)
                    return _translations;

                _translations = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

                if (!File.Exists(filePath))
                {
                    return _translations;
                }

                using (var reader = new StreamReader(filePath))
                {
                    string line;
                    while ((line = reader.ReadLine()) != null)
                    {
                        line = line.Trim();
                        if (line.Length < 2 || line[0] != '[')
                            continue;

                        string original = null;
                        string translated = null;
                        if (ParseNDJSONLine(line, out original, out translated))
                        {
                            if (!string.IsNullOrEmpty(original) && !string.IsNullOrEmpty(translated))
                            {
                                _translations[original] = translated;
                            }
                        }
                    }
                }

                return _translations;
            }
        }

        private static bool ParseNDJSONLine(string line, out string original, out string translated)
        {
            original = null;
            translated = null;

            try
            {
                int idx = 0;
                if (line[idx] == '[') idx++;

                // skip source_seq (first quoted field)
                idx = SkipQuotedField(line, idx);
                if (idx < 0) return false;
                idx = SkipWhitespaceComma(line, idx);

                // read original (second quoted field)
                int origStart = idx;
                idx = SkipQuotedField(line, idx);
                if (idx < 0) return false;
                original = UnescapeJSON(line.Substring(origStart + 1, idx - origStart - 2));
                idx = SkipWhitespaceComma(line, idx);

                // read translated (third quoted field)
                int transStart = idx;
                idx = SkipQuotedField(line, idx);
                if (idx < 0) return false;
                translated = UnescapeJSON(line.Substring(transStart + 1, idx - transStart - 2));

                return true;
            }
            catch
            {
                return false;
            }
        }

        private static int SkipQuotedField(string s, int start)
        {
            if (start >= s.Length || s[start] != '"')
                return -1;
            int i = start + 1;
            while (i < s.Length)
            {
                if (s[i] == '\\') i += 2;
                else if (s[i] == '"') return i + 1;
                else i++;
            }
            return -1;
        }

        private static int SkipWhitespaceComma(string s, int start)
        {
            int i = start;
            while (i < s.Length && (s[i] == ',' || s[i] == ' '))
                i++;
            return i;
        }

        private static string UnescapeJSON(string s)
        {
            return s.Replace("\\\"", "\"").Replace("\\\\", "\\");
        }
    }
}
