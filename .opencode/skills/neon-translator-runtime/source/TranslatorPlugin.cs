using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace NeonTranslator
{
    public static class TranslatorPlugin
    {
        private static Dictionary<string, string> _translations;
        private static bool _initialized;
        private static string _logPath;
        private static List<Component> _cachedTextComponents;
        private static bool _cacheValid = false;
        private static bool _translationSystemPatched = false;

        private static string GetLogPath()
        {
            if (_logPath == null)
            {
                string dllPath = Assembly.GetExecutingAssembly().Location;
                string dllDir = Path.GetDirectoryName(dllPath);
                _logPath = Path.Combine(dllDir, "NeonTranslator.log");
            }
            return _logPath;
        }

        internal static void Log(string message)
        {
            try { File.AppendAllText(GetLogPath(), message + "\n"); } catch { }
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Initialize()
        {
            try
            {
                Log("Init at " + DateTime.Now);

                if (!_initialized)
                {
                    _initialized = true;
                    string dllPath = Assembly.GetExecutingAssembly().Location;
                    string dllDir = Path.GetDirectoryName(dllPath);
                    string dataPath = Path.Combine(dllDir, "NeonTranslatorRuntime_Data.ndjson");
                    _translations = TranslationLoader.Load(dataPath);
                    Log("Translations: " + (_translations != null ? _translations.Count.ToString() : "null"));
                }

                SceneManager.sceneLoaded += OnSceneLoaded;
                Canvas.willRenderCanvases += FastScan;
                Log("Init done");

                TryPatchTranslationSystem();
                PopulateAllText();
                FastScan();
            }
            catch (Exception ex)
            {
                Log("ERROR: " + ex.ToString());
            }
        }

        private static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            _cacheValid = false;
            TryPatchTranslationSystem();
            PopulateAllText();
            FastScan();
        }

        private static string GetText(Component c)
        {
            if (c == null) return null;
            var prop = c.GetType().GetProperty("text");
            if (prop == null) return null;
            return prop.GetValue(c) as string;
        }

        private static void SetText(Component c, string value)
        {
            if (c == null) return;
            var prop = c.GetType().GetProperty("text");
            if (prop == null) return;
            prop.SetValue(c, value);
        }

        private static List<Component> FindAllTextComponents()
        {
            var result = new List<Component>();
            var tmpType = GetType("TMPro.TMP_Text");
            if (tmpType != null)
            {
                var found = UnityEngine.Object.FindObjectsOfType(tmpType);
                foreach (var obj in found) result.Add((Component)obj);
            }
            var legacyType = GetType("UnityEngine.UI.Text");
            if (legacyType != null)
            {
                var found = UnityEngine.Object.FindObjectsOfType(legacyType);
                foreach (var obj in found) result.Add((Component)obj);
            }
            return result;
        }

        private static void TryPatchTranslationSystem()
        {
            if (_translationSystemPatched) return;

            var lmType = GetType("ANToolkit.Localization.LanguageManager");
            var lineType = GetType("ANToolkit.Localization.TranslationJsonLine");
            var uiLocType = GetType("ANToolkit.Localization.UILocalization");
            if (lmType == null || lineType == null || uiLocType == null) { Log("Patch: types not found"); return; }

            try
            {
                var dictField = lmType.GetField("_guidToTranslationDictionary",
                    BindingFlags.Static | BindingFlags.NonPublic);
                if (dictField == null) { Log("Patch: no dict field"); return; }

                var onLangChangedField = lmType.GetField("OnLanguageChanged",
                    BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
                if (onLangChangedField == null) { Log("Patch: no event field"); return; }

                var guidField = uiLocType.GetField("guid",
                    BindingFlags.Public | BindingFlags.Instance) ??
                    uiLocType.GetField("guid", BindingFlags.NonPublic | BindingFlags.Instance);
                if (guidField == null) { Log("Patch: no guid field"); return; }

                var tmpType = GetType("TMPro.TMP_Text");
                var legacyType = GetType("UnityEngine.UI.Text");

                var uiLocs = UnityEngine.Object.FindObjectsOfType(uiLocType);
                Log("Patch: " + uiLocs.Length + " UILoc components");

                var guidToEnglish = new Dictionary<string, string>();
                var guidToUiLoc = new Dictionary<string, object>();

                foreach (var uiLoc in uiLocs)
                {
                    string g = guidField.GetValue(uiLoc) as string;
                    if (string.IsNullOrEmpty(g)) continue;

                    var go = ((Component)uiLoc).gameObject;
                    Component textComp = null;
                    if (tmpType != null) textComp = go.GetComponent(tmpType);
                    if (textComp == null && legacyType != null) textComp = go.GetComponent(legacyType);
                    if (textComp == null && tmpType != null) textComp = go.GetComponentInChildren(tmpType);
                    if (textComp == null && legacyType != null) textComp = go.GetComponentInChildren(legacyType);
                    if (textComp == null) continue;

                    string txt = GetText(textComp);
                    if (string.IsNullOrEmpty(txt)) continue;

                    guidToEnglish[g] = txt;
                    guidToUiLoc[g] = uiLoc;
                }

                Log("Patch: " + guidToEnglish.Count + " GUID→English pairs");

                if (guidToEnglish.Count == 0) { Log("Patch: empty, will retry"); return; }

                var currentDict = dictField.GetValue(null) as IDictionary;
                if (currentDict == null)
                {
                    var outerDictType = typeof(Dictionary<string, IDictionary>);
                    currentDict = (IDictionary)Activator.CreateInstance(outerDictType);
                    dictField.SetValue(null, currentDict);
                }

                var innerDictType = typeof(Dictionary<,>).MakeGenericType(typeof(string), lineType);

                IDictionary englishDict = null;
                if (currentDict.Contains("English"))
                {
                    var existing = currentDict["English"];
                    if (existing != null) englishDict = existing as IDictionary;
                }
                if (englishDict == null)
                    englishDict = (IDictionary)Activator.CreateInstance(innerDictType);

                IDictionary russianDict = null;
                if (currentDict.Contains("Russian"))
                {
                    var existing = currentDict["Russian"];
                    if (existing != null) russianDict = existing as IDictionary;
                }
                if (russianDict == null)
                    russianDict = (IDictionary)Activator.CreateInstance(innerDictType);

                var lineIdField = lineType.GetField("lineId");
                var origTextField = lineType.GetField("originalText");
                var textField = lineType.GetField("text");
                int populated = 0;

                foreach (var kvp in guidToEnglish)
                {
                    string guid = kvp.Key;
                    string englishText = kvp.Value;

                    if (!_translations.ContainsKey(englishText))
                    {
                        Log("Patch: no translation for '" + englishText + "' GUID=" + guid);
                        continue;
                    }

                    string russianText = _translations[englishText];

                    var enLine = Activator.CreateInstance(lineType);
                    var ruLine = Activator.CreateInstance(lineType);

                    if (lineIdField != null)
                    {
                        lineIdField.SetValue(enLine, guid);
                        lineIdField.SetValue(ruLine, guid);
                    }
                    if (origTextField != null)
                    {
                        origTextField.SetValue(enLine, englishText);
                        origTextField.SetValue(ruLine, englishText);
                    }
                    if (textField != null)
                    {
                        textField.SetValue(enLine, englishText);
                        textField.SetValue(ruLine, russianText);
                    }

                    if (!englishDict.Contains(guid)) englishDict[guid] = enLine;
                    russianDict[guid] = ruLine;
                    populated++;
                }

                Log("Patch: populated " + populated + " Russian + " + englishDict.Count + " English entries");

                currentDict["English"] = englishDict;
                currentDict["Russian"] = russianDict;

                var unityEvent = onLangChangedField.GetValue(null);
                if (unityEvent != null)
                {
                    var invokeMethod = unityEvent.GetType().GetMethod("Invoke", Type.EmptyTypes);
                    if (invokeMethod != null)
                    {
                        invokeMethod.Invoke(unityEvent, null);
                        Log("Patch: OnLanguageChanged invoked");
                    }
                }

                _translationSystemPatched = true;
                Log("Patch: SUCCESS — translation system patched");
            }
            catch (Exception ex)
            {
                Log("Patch error: " + ex.ToString());
            }
        }

        public static string Translate(string original)
        {
            if (_translations != null && original != null)
            {
                string translated;
                if (_translations.TryGetValue(original, out translated))
                    return translated;
            }
            return null;
        }

        private static void PopulateAllText()
        {
            if (_translations == null) return;

            var allComponents = FindAllTextComponents();
            int replaced = 0;
            foreach (var c in allComponents)
            {
                if (c == null) continue;
                string current = GetText(c);
                if (string.IsNullOrEmpty(current)) continue;
                string translated;
                if (_translations.TryGetValue(current, out translated) && translated != current)
                {
                    SetText(c, translated);
                    replaced++;
                }
            }
            if (replaced > 0)
                Log("PopulateAll: replaced " + replaced);
        }

        private static void EnsureCache()
        {
            if (_cacheValid) return;
            _cachedTextComponents = FindAllTextComponents();
            _cacheValid = true;
        }

        private static int _fastScanCount = 0;

        private static void FastScan()
        {
            if (_translations == null) return;
            try
            {
                _fastScanCount++;
                if (_fastScanCount % 5 == 0) _cacheValid = false;
                EnsureCache();
                int replaced = 0;
                foreach (var c in _cachedTextComponents)
                {
                    if (c == null) continue;
                    string current = GetText(c);
                    if (string.IsNullOrEmpty(current)) continue;
                    string translated;
                    if (_translations.TryGetValue(current, out translated) && translated != current)
                    {
                        SetText(c, translated);
                        replaced++;
                    }
                }
                if (replaced > 0 && replaced < 5)
                    Log("FastScan: replaced " + replaced);
            }
            catch { }
        }

        private static Type GetType(string typeName)
        {
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                var t = asm.GetType(typeName);
                if (t != null) return t;
            }
            return null;
        }
    }
}
