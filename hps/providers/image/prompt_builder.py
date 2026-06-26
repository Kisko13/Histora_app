def build_historical_prompt(block):
    text = (block["text"] or "").replace("\n", " ")
    image_prompt = block["image_prompt"] or ""
    return f'''Historical cinematic illustration for an immersive YouTube history video.

Scene: {block["scene_title"]}
Character focus: {block["character_id"]}

Block image direction:
{image_prompt}

Narration context:
{text[:900]}

Style:
Photorealistic historical reconstruction, grounded realism, cinematic but not fantasy, natural lighting, historically plausible Roman Republican equipment, immersive first-person documentary feeling.

Strict negatives:
No fantasy armor, no horned helmets, no modern objects, no guns, no glowing magic, no anime, no cartoon style, no text, no watermarks, no logos, no medieval equipment.'''.strip()
