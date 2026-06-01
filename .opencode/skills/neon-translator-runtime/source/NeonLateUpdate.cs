using UnityEngine;

namespace NeonTranslator
{
    [DefaultExecutionOrder(10000)]
    public class NeonLateUpdate : MonoBehaviour
    {
        private void LateUpdate()
        {
            TranslatorPlugin.PopulateAllTextPublic();
        }
    }
}
