import base64, json, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

def openai_image_config():
    return {
        "api_key": os.getenv("OPENAI_API_KEY", "").strip(),
        "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
        "size": os.getenv("OPENAI_IMAGE_SIZE", "1536x1024"),
        "quality": os.getenv("OPENAI_IMAGE_QUALITY", "medium"),
        "estimated_cost": float(os.getenv("ESTIMATED_OPENAI_IMAGE_COST_USD", "0.04") or "0.04"),
        "allow_paid": os.getenv("ALLOW_PAID_IMAGE_GENERATION", "false").lower() == "true",
    }

def check_openai_image_config():
    cfg = openai_image_config()
    missing = []
    if not cfg["api_key"]:
        missing.append("OPENAI_API_KEY")
    return {"ok": not missing, "missing": missing, "config": {k: ("***" if k=="api_key" and v else v) for k,v in cfg.items()}}

def create_openai_image(prompt, output_path: Path, dry_run=True):
    cfg = openai_image_config()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"model": cfg["model"], "prompt": prompt, "size": cfg["size"], "quality": cfg["quality"]}
    if dry_run:
        sidecar = output_path.with_suffix(".dryrun.json")
        sidecar.write_text(json.dumps({"endpoint":"not called - dry run", "payload":payload}, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "dry_run": True, "payload_sidecar": str(sidecar), "status": "dry_run"}
    if not cfg["allow_paid"]:
        raise RuntimeError("Paid image generation blocked. Set ALLOW_PAID_IMAGE_GENERATION=true only when ready.")
    if not cfg["api_key"]:
        raise RuntimeError("Missing OPENAI_API_KEY.")
    from openai import OpenAI
    client = OpenAI(api_key=cfg["api_key"])
    result = client.images.generate(model=cfg["model"], prompt=prompt, size=cfg["size"], quality=cfg["quality"])
    sidecar = output_path.with_suffix(".response.json")
    try:
        sidecar.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    except Exception:
        sidecar.write_text(str(result), encoding="utf-8")
    d = result.data[0]
    b64 = getattr(d, "b64_json", None)
    if b64:
        output_path.write_bytes(base64.b64decode(b64))
        return {"ok": True, "image_path": str(output_path), "response_sidecar": str(sidecar), "status": "generated"}
    url = getattr(d, "url", None)
    if url:
        import requests
        r = requests.get(url, timeout=180)
        if r.status_code == 200:
            output_path.write_bytes(r.content)
            return {"ok": True, "image_path": str(output_path), "response_sidecar": str(sidecar), "status": "generated"}
    return {"ok": False, "response_sidecar": str(sidecar), "status": "needs_inspection"}
