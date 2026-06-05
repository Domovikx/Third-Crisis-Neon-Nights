using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace NeonTranslator
{
    internal static class TranslationLoader
    {
        private static Dictionary<string, string> _translations;
        private static HashSet<string> _allKeys;
        private static object _lock = new object();

        public static Dictionary<string, string> Load(string dirPath)
        {
            lock (_lock)
            {
                if (_translations != null)
                    return _translations;

                _translations = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                _allKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

                if (!Directory.Exists(dirPath))
                    return _translations;

                // Recursively find all *.yaml files
                string[] files = Directory.GetFiles(dirPath, "*.yaml", SearchOption.AllDirectories);
                Array.Sort(files);

                foreach (string filePath in files)
                {
                    try
                    {
                        ParseYamlFile(filePath);
                    }
                    catch
                    {
                        // skip corrupt files
                    }
                }

                return _translations;
            }
        }

        private static void ParseYamlFile(string filePath)
        {
            string[] lines = File.ReadAllLines(filePath);
            var entryLines = new List<string>();
            bool inEntry = false;

            foreach (string rawLine in lines)
            {
                string line = rawLine.Trim();

                // Skip comments and blank lines
                if (line.Length == 0 || line[0] == '#')
                {
                    if (inEntry)
                    {
                        // This shouldn't happen in valid YAML, but handle gracefully
                        ProcessEntry(entryLines);
                        entryLines.Clear();
                        inEntry = false;
                    }
                    continue;
                }

                // Detect start of a list entry: "- ["
                if (!inEntry && line.StartsWith("- ["))
                {
                    inEntry = true;
                    entryLines.Clear();
                    entryLines.Add(line);
                    if (line.EndsWith("]"))
                    {
                        ProcessEntry(entryLines);
                        entryLines.Clear();
                        inEntry = false;
                    }
                    continue;
                }

                // Accumulate multi-line entries
                if (inEntry)
                {
                    entryLines.Add(line);
                    if (line.Contains("]"))
                    {
                        ProcessEntry(entryLines);
                        entryLines.Clear();
                        inEntry = false;
                    }
                }
            }
        }

        private static void ProcessEntry(List<string> entryLines)
        {
            // Join accumulated lines into one string
            StringBuilder sb = new StringBuilder();
            foreach (string l in entryLines)
            {
                sb.Append(l.Trim());
            }
            string combined = sb.ToString();

            // Remove "- [" prefix and "]" suffix
            int start = combined.IndexOf('[');
            int end = combined.LastIndexOf(']');
            if (start < 0 || end < 0 || end <= start)
                return;

            string inner = combined.Substring(start + 1, end - start - 1);

            // Parse quoted values: split on "," but respect escaping
            var values = new List<string>();
            int i = 0;
            while (i < inner.Length)
            {
                // Find opening quote
                int qi = inner.IndexOf('"', i);
                if (qi < 0) break;

                // Find closing quote (skip escaped \")
                int qj = qi + 1;
                while (qj < inner.Length)
                {
                    if (inner[qj] == '\\')
                    {
                        qj += 2; // skip escaped char
                        continue;
                    }
                    if (inner[qj] == '"')
                        break;
                    qj++;
                }
                if (qj >= inner.Length) break;

                // Extract value between quotes
                string val = inner.Substring(qi + 1, qj - qi - 1);
                val = val.Replace("\\\"", "\"").Replace("\\\\", "\\");
                values.Add(val);

                i = qj + 1;
            }

            if (values.Count < 2) return;
            if (string.IsNullOrEmpty(values[0])) return;

            string key = values[0];
            string translation = values[1];

            _allKeys.Add(key);
            if (!string.IsNullOrEmpty(translation))
            {
                _translations[key] = translation;
            }
        }

        public static bool IsKnownKey(string key)
        {
            return _allKeys != null && _allKeys.Contains(key);
        }
    }
}
