using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Threading;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace NeonTranslator
{
    public static class TranslatorPlugin
    {
        private static Dictionary<string, string> _translations;
        private static bool _initialized;
        private static string _logPath;
        private static Timer _scanTimer;

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
                Log("Initialize() at " + DateTime.Now);

                if (!_initialized)
                {
                    _initialized = true;
                    string dllPath = Assembly.GetExecutingAssembly().Location;
                    string dllDir = Path.GetDirectoryName(dllPath);
                    string dataPath = Path.Combine(dllDir, "NeonTranslatorRuntime_Data.ndjson");
                    _translations = TranslationLoader.Load(dataPath);
                    Log("Translations loaded: " + (_translations != null ? _translations.Count.ToString() : "null"));
                }

                TranslateExistingText();
                Log("Initial scan done");

                SceneManager.sceneLoaded += OnSceneLoaded;
                Log("Registered sceneLoaded handler");

                // Set up periodic timer via Unity SynchronizationContext
                var syncCtx = SynchronizationContext.Current;
                if (syncCtx != null)
                {
                    _scanTimer = new Timer(_ =>
                    {
                        try { syncCtx.Post(__ => { TranslateExistingText(); }, null); }
                        catch { }
                    }, null, 500, 500);
                    Log("Timer started via SynchronizationContext");
                }
                else
                {
                    Log("WARN: SynchronizationContext.Current is null, no periodic scan");
                }
            }
            catch (Exception ex)
            {
                Log("ERROR: " + ex.ToString());
            }
        }

        private static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            Log("Scene loaded: " + scene.name + " mode=" + mode);
            TranslateExistingText();
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

        public static void TranslateExistingText()
        {
            if (_translations == null) return;

            int count = 0;
            int logged = 0;

            try
            {
                var tmproType = GetType("TMPro.TMP_Text");
                if (tmproType != null)
                {
                    var textProp = tmproType.GetProperty("text");
                    if (textProp != null)
                    {
                        var allTmpro = UnityEngine.Object.FindObjectsOfType(tmproType);
                        foreach (var obj in allTmpro)
                        {
                            string current = textProp.GetValue(obj, null) as string;
                            if (string.IsNullOrEmpty(current)) continue;
                            if (logged < 30) { Log("TEXT: '" + current + "'"); logged++; }
                            string translated = Translate(current);
                            if (translated != null)
                            {
                                textProp.SetValue(obj, translated, null);
                                count++;
                            }
                        }
                    }
                }
            }
            catch (Exception ex) { Log("TranslateExistingText TMP error: " + ex.Message); }

            try
            {
                var uiTextType = GetType("UnityEngine.UI.Text");
                if (uiTextType != null)
                {
                    var textProp = uiTextType.GetProperty("text");
                    if (textProp != null)
                    {
                        var allUiText = UnityEngine.Object.FindObjectsOfType(uiTextType);
                        foreach (var obj in allUiText)
                        {
                            string current = textProp.GetValue(obj, null) as string;
                            if (string.IsNullOrEmpty(current)) continue;
                            if (logged < 30) { Log("TEXT: '" + current + "'"); logged++; }
                            string translated = Translate(current);
                            if (translated != null)
                            {
                                textProp.SetValue(obj, translated, null);
                                count++;
                            }
                        }
                    }
                }
            }
            catch (Exception ex) { Log("TranslateExistingText UI error: " + ex.Message); }

            if (count > 0) Log("Translated " + count + " texts in scan");
            if (logged == 0 && count == 0) Log("NO texts found in scan");
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
