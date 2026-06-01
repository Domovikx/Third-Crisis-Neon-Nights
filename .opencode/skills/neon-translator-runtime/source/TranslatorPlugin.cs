using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace NeonTranslator
{
    public static class TranslatorPlugin
    {
        private static Dictionary<string, string> _translations;
        private static bool _initialized;
        private static string _logPath;

        private static List<Component> _cachedComponents;
        private static bool _cacheValid = false;
        private static Type _lmType;
        private static Type _lineType;
        private static Type _uiLocType;
        private static Type _tmpType;
        private static Type _legacyType;

        private static FieldInfo _dictField;
        private static FieldInfo _onLangChangedField;
        private static FieldInfo _guidField;
        private static FieldInfo _origTextField;
        private static FieldInfo _lineIdField;
        private static FieldInfo _origTextJsonField;
        private static FieldInfo _textJsonField;

        private static FieldInfo _textMTextField;
        private static FieldInfo _tmpMTextField;
        private static FieldInfo _tmpHavePropChangedField;

        private static MethodInfo _setTextMethod;
        private static IDictionary _guidDict;
        private static bool _reflectionReady = false;

        private static string GetLogPath()
        {
            string dllPath = Assembly.GetExecutingAssembly().Location;
            string dllDir = Path.GetDirectoryName(dllPath);
            return Path.Combine(dllDir, "NeonTranslator.log");
        }

        internal static void Log(string message)
        {
            try { File.AppendAllText(GetLogPath(), message + "\n"); } catch { }
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

                InitReflection();
                SceneManager.sceneLoaded += OnSceneLoaded;
                Canvas.willRenderCanvases += OnPreRender;

                var go = new GameObject("NeonTranslator_Scanner");
                go.hideFlags = HideFlags.HideAndDontSave;
                GameObject.DontDestroyOnLoad(go);
                go.AddComponent<NeonLateUpdate>();

                Log("Init done");
                DumpAllTextComponents();

                ScanAllUiLocs();
                InvalidateCache();
                PopulateAllText();
            }
            catch (Exception ex)
            {
                Log("ERROR: " + ex.ToString());
            }
        }

        private static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            InvalidateCache();
            ScanAllUiLocs();
            PopulateAllText();
        }

        private static void InitReflection()
        {
            if (_reflectionReady) return;
            _lmType = GetType("ANToolkit.Localization.LanguageManager");
            _lineType = GetType("ANToolkit.Localization.TranslationJsonLine");
            _uiLocType = GetType("ANToolkit.Localization.UILocalization");
            _tmpType = GetType("TMPro.TMP_Text");
            _legacyType = GetType("UnityEngine.UI.Text");

            if (_lmType == null || _lineType == null || _uiLocType == null)
            { Log("Refl: types not found"); return; }

            _dictField = _lmType.GetField("_guidToTranslationDictionary",
                BindingFlags.Static | BindingFlags.NonPublic);
            _onLangChangedField = _lmType.GetField("OnLanguageChanged",
                BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
            _guidField = _uiLocType.GetField("guid",
                BindingFlags.Public | BindingFlags.Instance) ??
                _uiLocType.GetField("guid", BindingFlags.NonPublic | BindingFlags.Instance);
            _origTextField = _uiLocType.GetField("_originalText",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);

            _lineIdField = _lineType.GetField("lineId");
            _origTextJsonField = _lineType.GetField("originalText");
            _textJsonField = _lineType.GetField("text");

            _setTextMethod = _uiLocType.GetMethod("SetTextToTranslation",
                BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);

            if (_dictField == null || _guidField == null)
            { Log("Refl: fields not found"); return; }

            if (_legacyType != null)
                _textMTextField = _legacyType.GetField("m_Text",
                    BindingFlags.Instance | BindingFlags.NonPublic);
            if (_tmpType != null)
                _tmpMTextField = _tmpType.GetField("m_text",
                    BindingFlags.Instance | BindingFlags.NonPublic) ??
                    _tmpType.GetField("m_Text",
                    BindingFlags.Instance | BindingFlags.NonPublic);
            if (_tmpType != null)
                _tmpHavePropChangedField = _tmpType.GetField("m_havePropertiesChanged",
                    BindingFlags.Instance | BindingFlags.NonPublic);

            _reflectionReady = true;
            Log("Refl: ready");
        }

        private static IDictionary GetOrCreateGuidDict()
        {
            if (_guidDict != null) return _guidDict;
            var val = _dictField.GetValue(null) as IDictionary;
            if (val == null)
            {
                val = (IDictionary)Activator.CreateInstance(typeof(Dictionary<string, IDictionary>));
                _dictField.SetValue(null, val);
            }
            _guidDict = val;
            return val;
        }

        private static IDictionary GetLangDict(string lang)
        {
            var outer = GetOrCreateGuidDict();
            if (outer.Contains(lang))
            {
                var inner = outer[lang] as IDictionary;
                if (inner != null) return inner;
            }
            var innerDictType = typeof(Dictionary<,>).MakeGenericType(typeof(string), _lineType);
            var innerDict = (IDictionary)Activator.CreateInstance(innerDictType);
            outer[lang] = innerDict;
            return innerDict;
        }

        private static void SetJsonField(FieldInfo field, object obj, object val)
        {
            if (field != null) field.SetValue(obj, val);
        }

        private static void AddTranslation(string guid, string english, string russian)
        {
            var ruDict = GetLangDict("Russian");
            var enDict = GetLangDict("English");

            if (!ruDict.Contains(guid))
            {
                var ruLine = Activator.CreateInstance(_lineType);
                SetJsonField(_lineIdField, ruLine, guid);
                SetJsonField(_origTextJsonField, ruLine, english);
                SetJsonField(_textJsonField, ruLine, russian);
                ruDict[guid] = ruLine;
            }

            if (!enDict.Contains(guid))
            {
                var enLine = Activator.CreateInstance(_lineType);
                SetJsonField(_lineIdField, enLine, guid);
                SetJsonField(_origTextJsonField, enLine, english);
                SetJsonField(_textJsonField, enLine, russian);
                enDict[guid] = enLine;
            }
        }

        private static void TriggerLanguageChanged()
        {
            if (_onLangChangedField == null) return;
            var unityEvent = _onLangChangedField.GetValue(null);
            if (unityEvent == null) return;
            var invokeMethod = unityEvent.GetType().GetMethod("Invoke", Type.EmptyTypes);
            if (invokeMethod != null) invokeMethod.Invoke(unityEvent, null);
        }

        private static void ScanAllUiLocs()
        {
            if (!_reflectionReady) return;

            try
            {
                var uiLocs = UnityEngine.Object.FindObjectsOfType(_uiLocType, true);
                int added = 0;

                foreach (var uiLoc in uiLocs)
                {
                    string g = _guidField.GetValue(uiLoc) as string;
                    if (string.IsNullOrEmpty(g)) continue;

                    var go = ((Component)uiLoc).gameObject;
                    Component textComp = null;
                    if (_tmpType != null) textComp = go.GetComponent(_tmpType);
                    if (textComp == null && _legacyType != null) textComp = go.GetComponent(_legacyType);
                    if (textComp == null && _tmpType != null) textComp = go.GetComponentInChildren(_tmpType, true);
                    if (textComp == null && _legacyType != null) textComp = go.GetComponentInChildren(_legacyType, true);
                    if (textComp == null) continue;

                    string txt = GetText(textComp);
                    if (string.IsNullOrEmpty(txt)) continue;

                    if (_translations.ContainsKey(txt))
                    {
                        var outer = GetOrCreateGuidDict();
                        bool alreadyInRussian = false;
                        if (outer.Contains("Russian"))
                        {
                            var ruDict = outer["Russian"] as IDictionary;
                            if (ruDict != null && ruDict.Contains(g)) alreadyInRussian = true;
                        }

                        if (!alreadyInRussian)
                        {
                            AddTranslation(g, txt, _translations[txt]);
                            added++;
                        }
                    }
                }

                if (added > 0)
                {
                    Log("ScanAll: added " + added + " new GUID translations");
                    TriggerLanguageChanged();
                }
            }
            catch (Exception ex)
            {
                Log("ScanAll error: " + ex.Message);
            }
        }

        private static string GetText(Component c)
        {
            if (c == null) return null;
            var prop = c.GetType().GetProperty("text");
            if (prop == null) return null;
            return prop.GetValue(c) as string;
        }

        private static void SetTextFieldDirect(Component c, string value)
        {
            if (c == null) return;
            FieldInfo field = null;
            Type t = c.GetType();
            if (_legacyType != null && _legacyType.IsAssignableFrom(t)) field = _textMTextField;
            else if (_tmpType != null && _tmpType.IsAssignableFrom(t)) field = _tmpMTextField;
            if (field == null) return;
            field.SetValue(c, value);
            if (_tmpType != null && _tmpType.IsAssignableFrom(t))
            {
                if (_tmpHavePropChangedField != null)
                    _tmpHavePropChangedField.SetValue(c, true);
                var tmp = c as TMPro.TMP_Text;
                if (tmp != null) tmp.SetVerticesDirty();
            }
            else
            {
                var graphic = c as Graphic;
                if (graphic != null) graphic.SetVerticesDirty();
            }
        }

        private static List<Component> FindAllTextComponents()
        {
            var result = new List<Component>();
            if (_tmpType != null)
            {
                var found = UnityEngine.Object.FindObjectsOfType(_tmpType);
                foreach (var obj in found) result.Add((Component)obj);
            }
            if (_legacyType != null)
            {
                var found = UnityEngine.Object.FindObjectsOfType(_legacyType);
                foreach (var obj in found) result.Add((Component)obj);
            }
            return result;
        }

        private static int _logDetailCount = 0;

        private static void PopulateAllText()
        {
            if (_translations == null) return;

            if (!_cacheValid)
            {
                _cachedComponents = FindAllTextComponents();
                _cacheValid = true;
            }

            int replaced = 0;
            foreach (var c in _cachedComponents)
            {
                if (c == null) continue;
                string current = GetText(c);
                if (string.IsNullOrEmpty(current)) continue;
                string translated;
                if (_translations.TryGetValue(current, out translated) && translated != current)
                {
                    if (_logDetailCount < 30)
                    {
                        _logDetailCount++;
                        string path = GetTransformPath(c.transform);
                        Log("Populate: '" + current + "' -> '" + translated + "' on " + path);
                    }
                    SetTextFieldDirect(c, translated);
                    replaced++;
                }
            }
            if (replaced > 0 && (_logDetailCount < 30 || _logDetailCount % 10 == 0))
                Log("Populate: replaced " + replaced + " texts");
        }

        private static void InvalidateCache()
        {
            _cacheValid = false;
        }

        public static void PopulateAllTextPublic()
        {
            PopulateAllText();
        }

        private static void OnPreRender()
        {
            InvalidateCache();
            ScanAllUiLocs();
            PopulateAllText();
        }

        private static void DumpAllTextComponents()
        {
            try
            {
                var all = FindAllTextComponents();
                Log("Dump: found " + all.Count + " text components");
                int dumped = 0;
                foreach (var c in all)
                {
                    if (dumped >= 20) { Log("Dump: ... (" + (all.Count - dumped) + " more)"); break; }
                    string txt = GetText(c);
                    if (!string.IsNullOrEmpty(txt))
                    {
                        Log("Dump: [" + GetTransformPath(c.transform) + "] = '" + txt + "'");
                        dumped++;
                    }
                }
            }
            catch (Exception ex) { Log("Dump error: " + ex.Message); }
        }

        private static string GetTransformPath(Transform t)
        {
            if (t == null) return "null";
            string path = t.name;
            Transform p = t.parent;
            while (p != null)
            {
                path = p.name + "/" + path;
                p = p.parent;
            }
            return path;
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
