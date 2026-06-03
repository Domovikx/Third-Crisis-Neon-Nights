using System;
using System.Collections.Generic;
using System.IO;

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
                {
                    return _translations;
                }

                // Recursively find all *.ndjson files
                string[] files = Directory.GetFiles(dirPath, "*.ndjson", SearchOption.AllDirectories);
                Array.Sort(files); // alphabetical — later files override earlier ones

                foreach (string filePath in files)
                {
                    try
                    {
                        string[] lines = File.ReadAllLines(filePath);
                        foreach (string rawLine in lines)
                        {
                            string line = rawLine.Trim();
                            if (string.IsNullOrEmpty(line)) continue;
                            if (!line.StartsWith("[") || !line.EndsWith("]")) continue;

                            // Parse: ["key","val"] or ["key","val","..."]
                            // Find first "," => key, find second "," => val
                            int firstComma = line.IndexOf("\",\"");
                            if (firstComma < 0) continue;

                            string key = line.Substring(2, firstComma - 2); // skip ["

                            // Check if there's a third element: look for next ","
                            int secondComma = line.IndexOf("\",\"", firstComma + 1);
                            string val;
                            if (secondComma < 0)
                            {
                                // 2-element: ["key","val"]
                                val = line.Substring(firstComma + 3, line.Length - firstComma - 5);
                            }
                            else
                            {
                                // 3+ element: ["key","val","..."] — val is between first and second comma
                                val = line.Substring(firstComma + 3, secondComma - firstComma - 3);
                            }

                            if (!string.IsNullOrEmpty(key))
                            {
                                _allKeys.Add(key);
                                if (!string.IsNullOrEmpty(val))
                                {
                                    _translations[key] = val;
                                }
                            }
                        }
                    }
                    catch
                    {
                        // skip corrupt files
                    }
                }

                return _translations;
            }
        }

        public static bool IsKnownKey(string key)
        {
            return _allKeys != null && _allKeys.Contains(key);
        }
    }
}
