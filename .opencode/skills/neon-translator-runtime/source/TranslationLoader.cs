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

                string content = File.ReadAllText(filePath);
                ParseJsonObject(content, _translations);

                return _translations;
            }
        }

        private static void ParseJsonObject(string content, Dictionary<string, string> dict)
        {
            int i = 0;

            // skip whitespace + opening brace
            while (i < content.Length && (content[i] == '{' || content[i] == ' ' || content[i] == '\t' || content[i] == '\n' || content[i] == '\r'))
                i++;

            while (i < content.Length)
            {
                // skip whitespace + comma
                while (i < content.Length && (content[i] == ',' || content[i] == ' ' || content[i] == '\t' || content[i] == '\n' || content[i] == '\r'))
                    i++;

                // closing brace — done
                if (i >= content.Length || content[i] == '}')
                    break;

                // read quoted key
                if (content[i] != '"') break;
                int keyStart = i + 1;
                int keyEnd = FindQuoteEnd(content, keyStart);
                if (keyEnd < 0) break;
                string key = UnescapeJSON(content.Substring(keyStart, keyEnd - keyStart));
                i = keyEnd + 1;

                // skip colon + whitespace
                while (i < content.Length && (content[i] == ':' || content[i] == ' ' || content[i] == '\t' || content[i] == '\n' || content[i] == '\r'))
                    i++;

                // read quoted value
                if (i >= content.Length || content[i] != '"') break;
                int valStart = i + 1;
                int valEnd = FindQuoteEnd(content, valStart);
                if (valEnd < 0) break;
                string val = UnescapeJSON(content.Substring(valStart, valEnd - valStart));
                i = valEnd + 1;

                if (!string.IsNullOrEmpty(key) && !string.IsNullOrEmpty(val))
                {
                    dict[key] = val;
                }
            }
        }

        private static int FindQuoteEnd(string s, int start)
        {
            int i = start;
            while (i < s.Length)
            {
                if (s[i] == '\\') i += 2;
                else if (s[i] == '"') return i;
                else i++;
            }
            return -1;
        }

        private static string UnescapeJSON(string s)
        {
            return s.Replace("\\\"", "\"").Replace("\\\\", "\\");
        }
    }
}
