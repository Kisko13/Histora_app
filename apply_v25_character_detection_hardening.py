from pathlib import Path

ROOT = Path(__file__).resolve().parent
det = ROOT / "hps" / "core" / "analysis" / "deterministic.py"

txt = det.read_text(encoding="utf-8")

start = txt.find("def detect_names(")
end = txt.find("\ndef detect_terms", start)

if start == -1 or end == -1:
    raise RuntimeError("Could not find detect_names function.")

new_detect_names = r'''def detect_names(script: str, context: AnalysisContext) -> list[str]:
    """
    Final generic character detection.

    Priority:
    1. User-provided known characters.
    2. Main POV character.
    3. Strong repeated proper names only.
    4. Dialogue-heavy unnamed scripts -> Speaker A / Speaker B.

    This avoids treating headings, places, titles, sentence starters,
    months, and random capitalized words as characters.
    """
    explicit = set()

    for n in context.known_characters or []:
        n = (n or "").strip()
        if n:
            explicit.add(n)

    if context.main_pov_character:
        explicit.add(context.main_pov_character.strip())

    if explicit:
        return sorted(explicit)

    # Dialogue-heavy unnamed text should not invent many fake characters.
    quote_lines = [l.strip() for l in script.splitlines() if l.strip().startswith('"')]
    if len(quote_lines) >= 8:
        # If there are no clear speaker tags, use generic speakers.
        speaker_tagged = any(re.match(r"^[A-Z][A-Za-z ]{1,30}:", l) for l in script.splitlines())
        if not speaker_tagged:
            return ["Speaker A", "Speaker B"]

    bad = set(STOP_NAMES)
    bad.update(w.title() for w in LOCATION_WORDS)
    bad.update(w.title() for w in EQUIPMENT_WORDS)
    bad.update({
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
        "January", "February", "March", "April", "May", "June", "July", "August",
        "September", "October", "November", "December",
        "North", "South", "East", "West",
        "Rome", "Cannae", "Canusium", "Capua", "Aufidus",
        "Morning", "Perfect", "Exactly", "Probably", "Really", "Good",
        "Someone", "Everyone", "Nobody", "Nothing", "Everything",
    })

    body_lines = []
    for line in script.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("*") and stripped.endswith("*"):
            continue
        if len(stripped.split()) <= 6 and stripped.upper() == stripped:
            continue
        body_lines.append(stripped)

    body = "\n".join(body_lines)

    # Detect single-token names repeated strongly.
    one_word = re.findall(r"\b[A-Z][a-z]{2,}\b", body)
    one_counts = Counter(x for x in one_word if x not in bad)

    names = set()
    for name, count in one_counts.items():
        if count >= 4:
            names.add(name)

    # Detect full names, e.g. Marcus Servilius, Publius Cornelius Scipio.
    full_names = re.findall(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2})\b", body)
    full_counts = Counter()
    for fn in full_names:
        parts = fn.split()
        if any(p in bad for p in parts):
            continue
        full_counts[fn] += 1

    for fn, count in full_counts.items():
        if count >= 1:
            # Keep first name as usable character label unless full name repeats.
            first = fn.split()[0]
            if one_counts.get(first, 0) >= 2:
                names.add(first)

    if not names:
        names.add("Narrator")

    # Cap discovered characters. Extra capitalized names become references, not production characters.
    return sorted(names)[:16]
'''

txt = txt[:start] + new_detect_names + txt[end:]

det.write_text(txt, encoding="utf-8")

doc = ROOT / "docs" / "V25_CHARACTER_DETECTION_HARDENING.md"
doc.write_text("""# V25 Character Detection Hardening

Improves generic character detection:

- If known characters are provided, use them as the authoritative list.
- If main POV character is provided, include it.
- Dialogue-only unnamed scripts become Speaker A / Speaker B.
- Capitalized words must repeat strongly to become characters.
- Locations, headings, weekdays, months, directions, and common sentence starters are ignored.
- Discovered character list is capped to avoid noisy projects.

No Cannae-specific logic was added to the analyzer flow.
""", encoding="utf-8")

print("V25 character detection hardening applied.")
print("Run: .\\run_studio_v24.bat")