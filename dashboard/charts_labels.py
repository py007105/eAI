"""Text for Mihir's dashboard-charts package (explanations, chart legends, stats table, preview page).

Same style as labels.py: CHART_LABELS[lang][key], `hi` falls back to `en` for any key it does not
define. This file is separate from labels.py (which Mihir's assignment must not edit).
"""
CHART_LABELS = {
    "en": {
        # explain_words.py sentence templates
        "not_answering": "{s} is not answering.",
        "slow": "{s} responds {x:.1f} times slower than normal.",
        "errors": "{p:.0f}% of requests to {s} are failing.",
        "mem": "{s} memory is at {p:.0f}% of its limit.",
        "mem_rising_suffix": " It is rising about {q:.0f}% of the limit per minute.",
        "traffic": "{s} has {x:.1f} times its normal traffic.",
        "restarted": "{s} restarted recently.",
        "deployed": "A new release of {s} was deployed in the last 3 minutes.",

        # charts.py: legend names, axis titles, empty-chart message
        "feat_lat_ratio": "Latency (x normal)",
        "feat_rps_ratio": "Traffic (x normal)",
        "feat_error_ratio": "Errors (%)",
        "feat_mem_share": "Memory (%)",
        "axis_times_normal": "times normal",
        "axis_percent": "%",
        "axis_seconds_ago": "seconds ago",
        "no_chart_data": "No data yet",

        # charts.py: stats table
        "stat_metric": "Metric",
        "stat_n": "n",
        "stat_median": "median",
        "stat_min": "min",
        "stat_max": "max",
        "stat_detect_to_action": "Detection -> action (s)",
        "stat_action_to_verified": "Action -> verified recovery (s)",
        "stat_by_status": "Incidents by status",
        "stat_not_executed": "Incidents without an executed action",

        # preview_app.py
        "banner": "SYNTHETIC SAMPLE DATA - not live",
        "lang_en": "English",
        "lang_hi": "Hindi",
        "select_language": "Language",
        "select_service": "Service",
        "select_tick": "Tick",
        "preview_title": "Dashboard charts preview (synthetic)",
        "explanation_title": "What the numbers say",
        "no_sentences": "Nothing to report for this service at this tick.",
    },
    "hi": {
        "not_answering": "{s} जवाब नहीं दे रहा है।",
        "slow": "{s} सामान्य से {x:.1f} गुना धीमा है।",
        "errors": "{s} के {p:.0f}% अनुरोध विफल हो रहे हैं।",
        "mem": "{s} की मेमोरी सीमा के {p:.0f}% पर है।",
        "mem_rising_suffix": " यह हर मिनट सीमा का लगभग {q:.0f}% बढ़ रही है।",
        "traffic": "{s} पर सामान्य से {x:.1f} गुना ट्रैफ़िक है।",
        "restarted": "{s} हाल ही में फिर से शुरू हुआ।",
        "deployed": "{s} का नया संस्करण पिछले 3 मिनट में लगाया गया।",

        "feat_lat_ratio": "लेटेंसी",
        "feat_rps_ratio": "ट्रैफ़िक",
        "feat_error_ratio": "त्रुटियाँ",
        "feat_mem_share": "मेमोरी",
        "axis_times_normal": "सामान्य का गुना",
        "axis_percent": "%",
        "axis_seconds_ago": "सेकंड पहले",
        "no_chart_data": "अभी कोई डेटा नहीं",

        "stat_metric": "मापदंड",
        "stat_by_status": "स्थिति अनुसार घटनाएँ",
        "stat_not_executed": "बिना कार्रवाई वाली घटनाएँ",
        "stat_detect_to_action": "पहचान से कार्रवाई (सेकंड)",
        "stat_action_to_verified": "कार्रवाई से सत्यापित रिकवरी (सेकंड)",

        "banner": "सिंथेटिक सैंपल डेटा - लाइव नहीं",
        "lang_hi": "हिन्दी",
        "select_language": "भाषा",
        "select_service": "सेवा",
        "select_tick": "टिक",
        "preview_title": "डैशबोर्ड चार्ट पूर्वावलोकन (सिंथेटिक)",
        "explanation_title": "आंकड़े क्या कहते हैं",
        "no_sentences": "इस सेवा के लिए इस टिक पर कुछ नहीं दिखाना है।",
    },
}


def ct(key: str, lang: str = "en") -> str:
    return CHART_LABELS.get(lang, {}).get(key) or CHART_LABELS["en"].get(key, key)
