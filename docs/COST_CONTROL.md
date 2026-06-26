# Cost Control

The in-app Production Assistant is local/rule-based.

It does not call:
- Qwen
- OpenAI
- any paid API

Qwen should only be used for:
- voice generation
- voice cloning

Default `.env`:

```env
ALLOW_PAID_GENERATION=false
MAX_BUILD_COST_USD=1.00
ESTIMATED_QWEN_COST_PER_1K_CHARS=0.015
```

To test safely, use provider:

```text
mock
```

Mock mode is free.

Paid generation is blocked unless you manually set:

```env
ALLOW_PAID_GENERATION=true
```

Even then, generation is blocked if estimated cost exceeds `MAX_BUILD_COST_USD`.
