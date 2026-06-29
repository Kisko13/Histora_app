from pathlib import Path

p = Path("studio_qt.py")
lines = p.read_text(encoding="utf-8").splitlines()

out = []
inside = False

for line in lines:
    stripped = line.lstrip()

    if stripped.startswith("def build_episode(self):"):
        out.append("    def build_episode(self):")
        inside = True
        continue

    if inside and stripped.startswith("def approve_latest(self):"):
        out.append("    def approve_latest(self):")
        inside = False
        continue

    if inside:
        if stripped:
            out.append("        " + stripped)
        else:
            out.append("")
    else:
        out.append(line)

p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("Fixed build_episode indentation.")