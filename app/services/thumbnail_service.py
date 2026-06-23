import os
import httpx
import logging
from decimal import Decimal
from app.core.config import settings
from app.utils.thumbnail_fallback import generate_pil_thumbnail

logger = logging.getLogger("api")

class ThumbnailService:
    """Service to handle generating, storing, and managing YouTube thumbnail drafts."""

    def __init__(self):
        self.cf_ai_url = settings.CF_AI_URL
        self.timeout = 45.0

    async def generate_options(
        self, 
        screenshot_path: str, 
        channel_name: str, 
        genre: str,
        style_prompt: str,
        video_title: str,
        video_id: int,
        channel_folder_path: str
    ) -> list[dict]:
        """Generate 3 thumbnail draft options using Cloudflare Workers AI with fallback to PIL.
        
        Returns:
            list[dict]: A list of generated thumbnail specifications ready to save to database.
        """
        # Ensure directories exist
        generated_dir = os.path.join(channel_folder_path, "thumbnails", "generated")
        os.makedirs(generated_dir, exist_ok=True)

        options = []
        
        # Build prompt variations to get distinct options
        prompt_variations = [
            f"{style_prompt}, masterpiece, 8k resolution, highly detailed",
            f"{style_prompt}, cinematic lighting, vibrant colors, artistic",
            f"{style_prompt}, minimalist composition, soft gradients, clean aesthetics"
        ]

        # Tier 1: Try Cloudflare Workers AI
        logger.info(f"Attempting Cloudflare AI thumbnail generation for video ID {video_id}")
        
        for i, prompt in enumerate(prompt_variations):
            option_filename = f"vid_{video_id}_thumb_option_{i + 1}.jpg"
            option_path = os.path.join(generated_dir, option_filename)
            
            success = await self._generate_cf_ai_image(screenshot_path, prompt, option_path)
            if success:
                options.append({
                    "image_path": option_path,
                    "style_name": settings.TZ,  # or custom style label
                    "prompt_used": prompt,
                    "confidence_score": Decimal("85.00"),  # Baseline high confidence for successful AI gen
                    "is_selected": (i == 0)  # Select option 1 by default
                })
            else:
                logger.warning(f"Cloudflare AI failed for option {i + 1}. Breaking to use local PIL fallback.")
                break

        # Tier 2: Local PIL Fallback (if CF AI failed to generate all 3 options)
        if len(options) < 3:
            logger.info("Falling back to local PIL overlay generation (Tier 2)")
            options.clear()  # Clear any partial success to ensure consistency
            
            option_filename = f"vid_{video_id}_thumb_fallback.jpg"
            option_path = os.path.join(generated_dir, option_filename)
            
            try:
                # Read screenshot and generate overlay
                image_bytes = generate_pil_thumbnail(
                    screenshot_path=screenshot_path,
                    title=video_title,
                    channel_name=channel_name,
                    genre=genre
                )
                with open(option_path, "wb") as f:
                    f.write(image_bytes)
                
                # Register a single high-quality fallback option
                options.append({
                    "image_path": option_path,
                    "style_name": "pil_fallback",
                    "prompt_used": "Local Pillow layout with title overlay",
                    "confidence_score": Decimal("75.00"),
                    "is_selected": True
                })
            except Exception as e:
                logger.error(f"PIL fallback overlay failed: {e}. Falling back to Tier 3: raw screenshot.")

        # Tier 3: Use Raw Screenshot directly
        if not options:
            logger.info("Falling back to raw frame-30 screenshot (Tier 3)")
            option_filename = f"vid_{video_id}_thumb_raw.jpg"
            option_path = os.path.join(generated_dir, option_filename)
            
            try:
                # Simply copy raw screenshot to target path
                import shutil
                shutil.copy2(screenshot_path, option_path)
                
                options.append({
                    "image_path": option_path,
                    "style_name": "raw_screenshot",
                    "prompt_used": "Raw extracted video frame at second 30",
                    "confidence_score": Decimal("50.00"),
                    "is_selected": True
                })
            except Exception as e:
                logger.critical(f"All thumbnail options and fallbacks failed: {e}")
                
        return options

    async def _generate_cf_ai_image(self, screenshot_path: str, prompt: str, output_path: str) -> bool:
        """Call external Workers AI endpoint to restyle screenshot."""
        if not self.cf_ai_url or "dummy" in self.cf_ai_url:
            return False  # Skip if URL is placeholder

        try:
            async with httpx.AsyncClient() as client:
                with open(screenshot_path, "rb") as f:
                    files = {"image": ("screenshot.jpg", f, "image/jpeg")}
                    data = {
                        "prompt": prompt,
                        "strength": "0.7",
                        "guidance": "7.5"
                    }
                    response = await client.post(
                        self.cf_ai_url,
                        files=files,
                        data=data,
                        timeout=self.timeout
                    )
                if response.status_code == 200 and len(response.content) > 1000:
                    with open(output_path, "wb") as out:
                        out.write(response.content)
                    return True
                else:
                    logger.warning(f"Workers AI returned code {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Workers AI API request failed: {e}")
            return False
