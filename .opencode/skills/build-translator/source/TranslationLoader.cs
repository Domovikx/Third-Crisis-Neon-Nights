using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

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
            var fields = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            bool inEntry = false;

            foreach (string rawLine in lines)
            {
                string trimmed = rawLine.Trim();

                // Skip comments and blank lines
                if (trimmed.Length == 0 || trimmed[0] == '#')
                {
                    if (inEntry)
                    {
                        ProcessEntry(fields);
                        fields.Clear();
                        inEntry = false;
                    }
                    continue;
                }

                // Detect entry start: "- key: value"
                if (trimmed.StartsWith("- "))
                {
                    if (inEntry)
                    {
                        ProcessEntry(fields);
                        fields.Clear();
                    }
                    inEntry = true;

                    // Parse key:value after "- "
                    string rest = trimmed.Substring(2).Trim();
                    ParseField(rest, fields);
                    continue;
                }

                // Continuation line (indented with 2+ spaces)
                if (inEntry && rawLine.StartsWith("  "))
                {
                    ParseField(trimmed, fields);
                }
            }

            // Last entry
            if (inEntry)
            {
                ProcessEntry(fields);
            }
        }

        private static void ParseField(string text, Dictionary<string, string> fields)
        {
            // Format: key: "value"  or  key: 'value'
            int colon = text.IndexOf(':');
            if (colon < 0) return;

            string key = text.Substring(0, colon).Trim();
            if (string.IsNullOrEmpty(key)) return;

            string rest = text.Substring(colon + 1).Trim();
            if (rest.Length < 2) return;

            char quote = rest[0];
            if (quote != '"' && quote != '\'') return;

            // Find closing quote respecting escaping
            int i = 1;
            while (i < rest.Length)
            {
                if (rest[i] == '\\')
                {
                    i += 2;
                    continue;
                }
                if (rest[i] == quote)
                {
                    string val = rest.Substring(1, i - 1);
                    val = val.Replace("\\\"", "\"").Replace("\\\\", "\\");
                    fields[key] = val;
                    return;
                }
                i++;
            }
        }

        private static readonly Regex _richTagRx = new Regex("<[^>]+>", RegexOptions.Compiled);

        private static void ProcessEntry(Dictionary<string, string> fields)
        {
            string text = GetField(fields, "text");
            if (string.IsNullOrEmpty(text))
                return;

            // Skip if already processed (defense-in-depth against duplicate keys)
            if (_allKeys.Contains(text))
                return;

            string translation = GetField(fields, "translation");
            string richText = GetField(fields, "rich_text");
            string richTranslation = GetField(fields, "rich_translation");

            // Auto-generate rich_translation from rich_text + translation when missing
            if (string.IsNullOrEmpty(richTranslation) && !string.IsNullOrEmpty(richText)
                && !string.IsNullOrEmpty(translation))
            {
                string plainFromRich = _richTagRx.Replace(richText, "");
                if (!string.IsNullOrEmpty(plainFromRich) && richText.Contains(plainFromRich))
                {
                    richTranslation = richText.Replace(plainFromRich, translation);
                }
            }

            // Best available: rich_translation > translation > rich_text > text
            string best = Coalesce(richTranslation, translation, richText, text);

            _allKeys.Add(text);
            if (!string.IsNullOrEmpty(best) && best != text)
            {
                _translations[text] = best;
            }
        }

        private static string GetField(Dictionary<string, string> fields, string key)
        {
            string val;
            if (fields.TryGetValue(key, out val))
                return val ?? "";
            return "";
        }

        private static string Coalesce(params string[] values)
        {
            foreach (string v in values)
            {
                if (!string.IsNullOrEmpty(v))
                    return v;
            }
            return "";
        }

        public static bool IsKnownKey(string key)
        {
            return _allKeys != null && _allKeys.Contains(key);
        }
    }
}
