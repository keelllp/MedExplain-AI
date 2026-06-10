"""Compiled trigger patterns for the safety guard (dev-tunable).

Kept as a Python module (not YAML) so regex escaping is safe. INPUT_TRIGGERS gate the
user's REQUEST (refuse prohibited intents); the OUTPUT_* patterns scan GENERATED prose.

The OUTPUT patterns intentionally match NATURAL phrasings (not just literal templates):
diagnosis = an assertion cue + a condition term; doses include worded quantities and many
units (but never lab concentration units like g/dL); treatment includes indirect directives;
reassurance includes "everything looks great" style. The hedged phrase "may be associated
with" is deliberately NOT a cue, so KB-grounded educational text passes.
"""

from __future__ import annotations

import re

# --- INPUT guard: prohibited request intents (category, [patterns]); first match wins ---

_DIAGNOSIS = [
    r"\bdo i have\b",
    r"\bdiagnos(?:e|is|ed|ing)\b",
    r"\bwhat(?:'s| is) wrong with me\b",
    r"\b(?:could|might|can) (?:this|it|these|that) be\b",
    r"\bis (?:this|it) (?:a |an )?(?:cancer|serious|dangerous|fatal|benign|malignant|bad|diabetes|anemia|anaemia|an infection|a tumou?r|a disease|a condition)\b",
    r"\bwhat (?:disease|condition|illness)\b",
    r"\bam i (?:sick|dying|healthy|fine|ok|okay|normal)\b",
    r"\bis my (?:report|result|results|blood|test) (?:normal|ok|okay|fine|bad|serious)\b",
    r"\bshould i (?:be )?(?:worried|concerned|scared)\b",
    r"\bwill i die\b",
]
_DOSAGE = [
    r"\bhow (?:much|many)\b.{0,40}\b(?:should i (?:take|use|have)|do i (?:take|need|use))\b",
    r"\bwhat (?:is|are) the (?:dose|dosage)\b",
    r"\bwhat (?:dose|dosage)\b",
    r"\bdos(?:e|age) (?:of|for)\b",
    r"\bhow many\b.{0,20}\b(?:mg|ml|mcg|iu|tablets?|pills?|units?|capsules?|drops?)\b",
    r"\bhow often should i (?:take|use)\b",
]
_PRESCRIPTION = [
    r"\bwhat (?:medicine|medication|drug|pill|tablet|antibiotic|supplement)s? should i\b",
    r"\bshould i (?:take|start|stop|switch|continue)\b",
    r"\b(?:recommend|suggest|prescribe) (?:a |an |some )?(?:medicine|medication|drug|supplement|antibiotic|pill)\b",
    r"\bwhich (?:medicine|medication|drug|pill|antibiotic|supplement)\b",
    r"\bbest (?:medicine|medication|drug|supplement) for\b",
    r"\bwhat (?:drug|medicine|medication|pill) (?:treats|is for|for|helps|to take)\b",
    r"\bwhat can i take\b",
    r"\bdo i need (?:medication|medicine|a drug|drugs|treatment|antibiotics|surgery)\b",
]
_TREATMENT = [
    r"\bhow (?:do|can|should) i (?:cure|treat|fix|get rid of|reverse|manage|lower|raise|reduce|increase|improve)\b",
    r"\bhow to (?:cure|treat|fix|get rid of|reverse|lower|raise)\b",
    r"\bwhat (?:treatment|therapy|surgery|procedure)\b",
    r"\bwhat (?:is|are) the (?:treatment|cure|therapy|fix)s? (?:for|of|to)\b",
    r"\bshould i (?:get|have|undergo) (?:surgery|chemo|radiation|treatment|therapy)\b",
    r"\bwhat should i do (?:about|for) (?:my|this|these|the)\b",
]
_SELF_HARM = [
    r"\boverdose\b",
    r"\bhow much .{0,25}(?:lethal|to die|to overdose|to end)\b",
]

INPUT_TRIGGERS = [
    ("self_harm", [re.compile(p, re.I) for p in _SELF_HARM]),
    ("diagnosis", [re.compile(p, re.I) for p in _DIAGNOSIS]),
    ("dosage", [re.compile(p, re.I) for p in _DOSAGE]),
    ("prescription", [re.compile(p, re.I) for p in _PRESCRIPTION]),
    ("treatment", [re.compile(p, re.I) for p in _TREATMENT]),
]

# --- OUTPUT guard: prohibited content in GENERATED prose ---

# Condition terms (stems) for the diagnosis detector.
_CONDITION = (
    r"(?:diabet(?:es|ic)|anaemi\w*|anemi\w*|deficienc\w*|hypothyroid\w*|hyperthyroid\w*|"
    r"hypertensi\w*|thyroid (?:disease|disorder|condition)|cancer|leukaem?i\w*|tumou?r|"
    r"infection|disease|disorder|syndrome)"
)
# Assertion cues that, paired with a condition, assert a diagnosis (NOT the hedged
# "may be associated with", which is intentionally absent).
_DX_CUE = (
    r"(?:you (?:likely |probably )?(?:have|are)|you (?:appear|seem) to (?:have|be)|"
    r"this (?:is|confirms|means|indicates|shows)|these results? (?:indicate|suggest|confirm|show)|"
    r"(?:is|are) consistent with|consistent with|suggest(?:s|ive of)?|indicative of|"
    r"typical of|points to|diagnos)"
)
DIAGNOSTIC_RE = re.compile(_DX_CUE + r"\b.{0,40}?\b" + _CONDITION, re.I)

# Dose/quantity figures — but NOT lab concentration units (g/dL, mg/dL, ng/mL → "/" after).
_DOSE_UNIT = (
    r"(?:mg|milligrams?|mcg|µg|micrograms?|g|grams?|ml|millilit(?:re|er)s?|iu|units?|"
    r"tablets?|pills?|capsules?|drops?|tsp|teaspoons?|puffs?|sachets?)"
)
DOSE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*" + _DOSE_UNIT + r"\b(?!\s*/)"
    r"|\b(?:half a|one|two|three|four|five|a|a few|several)\s+"
    r"(?:tablets?|pills?|capsules?|doses?|teaspoons?|drops?|puffs?|sachets?)\b",
    re.I,
)

_MED = (
    r"(?:supplements?|medications?|medicines?|drugs?|therapy|statins?|metformin|"
    r"levothyroxine|insulin|antibiotics?|ferrous|iron (?:tablets?|pills?|supplements?))"
)
TREATMENT_RE = re.compile(
    r"\byou should (?:take|start|stop|get|undergo|have|begin|use|try)\b"
    r"|\b(?:start|stop|increase|decrease) (?:taking|using|your)\b"
    r"|\bconsider (?:taking|starting|trying|adding)\b"
    r"|\byou (?:may|might) want to (?:take|start|try|begin|consider|add)\b"
    r"|\bit (?:is|'s) (?:recommended|advised|best|important) to\b"
    r"|\btreatment with \w+"
    r"|\b(?:doctors?|physicians?|providers?) (?:usually |often |typically |may |might |will )?(?:prescribe|recommend|advise|start)\b"
    r"|\bmay help (?:to )?(?:raise|lower|treat|manage|improve|correct|boost|reduce)\b"
    r"|\b" + _MED + r"\b.{0,25}\bmay help\b"
    r"|\byou (?:need|require) (?:surgery|treatment|chemo|chemotherapy|radiation|medication|antibiotics)\b",
    re.I,
)

REASSURANCE_RE = re.compile(
    r"\byou(?:'re| are) (?:perfectly |completely )?(?:fine|healthy|okay|ok|normal)\b"
    r"|\b(?:everything|all|things) (?:looks?|is|are|seems?) (?:fine|great|good|normal|okay|ok)\b"
    r"|\b(?:your )?(?:results?|numbers?|values?) (?:are|look) (?:reassuring|good|great|normal|fine|okay|ok|healthy)\b"
    r"|\bnothing (?:serious|to (?:be )?(?:worry|worried|concern|concerned) about|wrong)\b"
    r"|\bnothing to worry about\b|\bno need to worry\b|\brest assured\b"
    r"|\b(?:a |this is (?:a )?)?(?:very |really )?(?:good|great|excellent) (?:result|news)\b",
    re.I,
)
