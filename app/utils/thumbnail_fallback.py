import os
import io
import textwrap
from PIL import Image, ImageDraw, ImageFont

def get_font(size: int = 40, bold: bool = False) -> ImageFont.ImageFont:
    """Attempt to load a standard system TrueType font for readable rendering.
    
    Falls back to the default pixel font if none are found.
    """
    font_paths = []
    if bold:
        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
        ]
    else:
        font_paths = [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
        ]

    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
                
    # Fallback to default
    return ImageFont.load_default()

def generate_pil_thumbnail(
    screenshot_path: str,
    title: str,
    channel_name: str,
    genre: str = "default"
) -> bytes:
    """Generate a high-quality fallback thumbnail using PIL overlays.
    
    Resizes screenshot to 1280x720, applies a dark gradient overlay at the bottom 
    for text readability, draws a genre-colored channel tag, and writes the video title.
    """
    # 1. Load and resize base image
    base_img = Image.open(screenshot_path).convert("RGBA").resize((1280, 720))
    
    # 2. Create gradient overlay for bottom readability
    overlay = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Draw a vertical gradient in the lower third
    for y in range(480, 720):
        # Alpha goes from 0 (at y=480) to 200 (at y=720)
        alpha = int((y - 480) / 240 * 200)
        draw.line([(0, y), (1280, y)], fill=(0, 0, 0, alpha))
        
    # 3. Combine base image and gradient
    img = Image.alpha_composite(base_img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    # 4. Set theme color based on channel genre
    genre_colors = {
        "lofi": (139, 157, 195),       # Muted blue-grey
        "jazz": (212, 163, 115),       # Warm gold
        "ambient": (168, 213, 186),    # Soft green
        "electronic": (199, 125, 255), # Purple
        "classical": (233, 196, 106),  # Yellow-gold
    }
    theme_color = genre_colors.get(genre.lower(), (220, 220, 220)) # Light grey default
    
    # 5. Draw Channel Name Badge (top-left)
    badge_x1, badge_y1 = 40, 40
    badge_x2, badge_y2 = 380, 85
    # Rounded badge background
    draw.rounded_rectangle(
        [(badge_x1, badge_y1), (badge_x2, badge_y2)], 
        radius=10, 
        fill=(15, 17, 21, 220), 
        outline=theme_color, 
        width=2
    )
    
    # Write Channel Name inside badge
    badge_font = get_font(size=20, bold=True)
    draw.text(
        (badge_x1 + 20, badge_y1 + 10), 
        channel_name.upper(), 
        fill=(255, 255, 255), 
        font=badge_font
    )
    
    # 6. Draw Wrapped Title Text (bottom)
    title_font = get_font(size=44, bold=True)
    wrapped_title = textwrap.fill(title, width=42)
    
    # Write title text with drop shadow (offset 3px)
    draw.text(
        (63, 523), 
        wrapped_title, 
        fill=(0, 0, 0), 
        font=title_font
    )
    draw.text(
        (60, 520), 
        wrapped_title, 
        fill=(255, 255, 255), 
        font=title_font
    )
    
    # 7. Save to bytes
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
