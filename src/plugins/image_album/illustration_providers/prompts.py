"""
Optimized prompts for converting photos to graphic illustrations.

Tuned for person/portrait photos to produce high-quality editorial-style illustrations
that work well on e-ink displays (good contrast, clean lines).
"""

# Primary prompt: best results for person/portrait → illustration
# Emphasizes: likeness retention, graphic style, e-ink friendly contrast
PERSON_ILLUSTRATION_PROMPT = (
    "Transform this portrait photo into a high-quality professional graphic illustration. "
    "Preserve the subject’s identity, facial structure, proportions, and expression with high accuracy. "
    "Style: modern editorial illustration, clean vector-like linework, smooth contours, "
    "flat color blocks with minimal gradients, bold yet controlled color palette. "
    "High contrast between subject and background, strong edge definition. "
    "Optimize for print and e-ink displays: limited colors, clear shapes, no visual noise. "
    "Soft, simple background or solid neutral backdrop. "
    "No photorealism, no painterly textures, no blur, no heavy shading, no background clutter."
)

# Fallback for non-person images (albums, landscapes, etc.)
GENERIC_ILLUSTRATION_PROMPT = (
    "Transform this image into a clean, professional graphic illustration. "
    "Style: modern editorial illustration, crisp linework, flat color areas, "
    "minimal gradients, simplified geometry. "
    "High contrast, strong silhouettes, and clear visual hierarchy. "
    "Optimize for print and e-ink displays: limited color palette, bold shapes, no noise. "
    "No photorealism, no complex textures, no cluttered background."
)

def get_illustration_prompt(is_person: bool = True) -> str:
    """Return the best prompt for the given image type."""
    return PERSON_ILLUSTRATION_PROMPT if is_person else GENERIC_ILLUSTRATION_PROMPT
