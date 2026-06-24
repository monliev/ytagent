import os
import logging
from decimal import Decimal
from typing import Optional, Any
from app.models.channel import Channel

logger = logging.getLogger("api")

class MetadataService:
    """Service to handle parsing filenames and auto-generating YouTube metadata drafts."""

    def parse_filename(self, filename: str) -> dict[str, str]:
        """Parse filename to extract mood, activity, genre, and duration hints.
        
        Example: 'lofi_relax_study_03h.mp4' -> {mood: 'relax', activity: 'study', genre: 'lofi', duration: '3 Hours'}
        """
        # Strip extension and replace common separators with spaces
        name, _ = os.path.splitext(filename)
        clean_name = name.replace("_", " ").replace("-", " ").lower()
        words = clean_name.split()

        # Default values
        hints = {
            "mood": "relaxing",
            "activity": "focus",
            "genre": "beats",
            "duration": "1 Hour"
        }

        # Dictionaries of known keywords
        moods = {"relax", "relaxing", "chill", "midnight", "focus", "peaceful", "dreamy", "ethereal", "sleep", "sad", "happy", "cosy", "warm"}
        activities = {"study", "sleep", "work", "code", "coding", "reading", "meditation", "gaming", "relax"}
        genres = {"lofi", "jazz", "ambient", "synthwave", "classical", "acoustic", "piano", "guitar"}

        # Look for duration hints (e.g. 3h, 1h, 30m, 180min)
        for word in words:
            if word.endswith("h") and word[:-1].isdigit():
                hints["duration"] = f"{word[:-1]} Hours" if int(word[:-1]) > 1 else "1 Hour"
            elif word.endswith("m") and word[:-1].isdigit():
                hints["duration"] = f"{word[:-1]} Minutes"
            elif word.endswith("min") and word[:-3].isdigit():
                hints["duration"] = f"{word[:-3]} Minutes"

        # Look for keywords
        found_moods = [w for w in words if w in moods]
        found_activities = [w for w in words if w in activities]
        found_genres = [w for w in words if w in genres]

        if found_moods:
            # Capitalize first found mood
            hints["mood"] = found_moods[0].capitalize()
        if found_activities:
            hints["activity"] = found_activities[0].capitalize()
        if found_genres:
            hints["genre"] = found_genres[0].capitalize()

        return hints

    def generate_draft(self, filename: str, channel: Channel, duration_seconds: int = 0) -> dict[str, Any]:
        """Auto-generate title, description, and tags draft for a video based on channel presets."""
        # 1. Parse hints
        hints = self.parse_filename(filename)
        
        # Override duration hint if precise duration is available from ffprobe
        if duration_seconds > 0:
            h = duration_seconds // 3600
            m = (duration_seconds % 3600) // 60
            if h > 0:
                hints["duration"] = f"{h} Hours" if h > 1 else "1 Hour"
            else:
                hints["duration"] = f"{m} Minutes"

        # 2. Build Title using template
        template = channel.preset_title_template or "{mood} {genre} Beats for {activity} | {duration}"
        
        title = template.format(
            mood=hints["mood"],
            activity=hints["activity"],
            genre=hints["genre"],
            duration=hints["duration"]
        )
        
        # Enforce YouTube's 100 character limit
        if len(title) > 100:
            title = title[:97] + "..."

        # 3. Build Description using template
        desc_template = channel.preset_description_template or (
            "Welcome to {channel_name}!\n\n"
            "Enjoy this selected {genre} mix, perfect for {activity}.\n\n"
            "Subscribe for more daily uploads!\n"
        )
        
        # Format base description
        description = desc_template.format(
            channel_name=channel.name,
            genre=hints["genre"],
            activity=hints["activity"]
        )

        # Append social links preset if configured
        if channel.preset_social_links:
            description += "\n--- Follow Us ---\n"
            for platform, url in channel.preset_social_links.items():
                description += f"{platform.capitalize()}: {url}\n"

        # Append genre hashtags
        description += f"\n#{channel.genre.lower()} #music #{hints['activity'].lower()} #{hints['mood'].lower()}"

        # 4. Compile Tags
        # Combine default tags from channel and keyword-based tags
        tags = list(channel.preset_tags) if channel.preset_tags else []
        extra_tags = [hints["mood"].lower(), hints["activity"].lower(), hints["genre"].lower(), "relaxing", "study music"]
        for tag in extra_tags:
            if tag not in tags:
                tags.append(tag)
                
        # Limit to 15 tags to prevent YouTube spam filters
        tags = tags[:15]

        # 5. Calculate Draft Confidence Score
        # High confidence if presets are complete, slightly lower if using general fallbacks
        base_confidence = 85.0
        if not channel.preset_title_template:
            base_confidence -= 10.0
        if not channel.preset_description_template:
            base_confidence -= 5.0
            
        confidence_score = Decimal(f"{max(50.0, base_confidence):.2f}")

        return {
            "title": title,
            "description": description,
            "tags": tags,
            "confidence_score": confidence_score
        }

    def generate_ai_draft(self, filename: str, channel: Channel, duration_seconds: int = 0) -> dict[str, Any]:
        """Generate title, description, tags, and Hermes review note using Cloudflare LLM.
        Falls back to rules-based generate_draft on error or if unconfigured.
        """
        # Get base fallback first
        fallback = self.generate_draft(filename, channel, duration_seconds)
        fallback["ai_review_note"] = "Hermes: Draf metadata dibuat menggunakan template default. Silakan sesuaikan lebih lanjut."
        
        from app.core.config import settings
        import httpx
        import json
        
        if not settings.CF_AI_URL or "dummy" in settings.CF_AI_URL:
            return fallback

        # Parse duration for prompt
        h = duration_seconds // 3600
        m = (duration_seconds % 3600) // 60
        duration_str = f"{h} Hours" if h > 0 else f"{m} Minutes"

        prompt = f"""
        You are Hermes, a professional YouTube growth strategist and automated co-pilot.
        Generate YouTube video metadata based on this video:
        Filename: {filename}
        Channel Name: {channel.name}
        Channel Niche/Genre: {channel.genre}
        Video Duration: {duration_str}

        Task:
        1. Write an engaging, high-CTR, SEO-friendly video Title (maximum 100 characters).
        2. Write a structured, readable video Description in Indonesian. Include:
           - A hook (first 2 lines)
           - A short summary of the video
           - A call-to-action (subscribe and like)
           - Relevant hashtags (3-5 tags) at the end.
        3. Compile a list of 10-15 highly relevant Tags (keywords).
        4. Write a concise "Hermes Review Note" (in Indonesian) evaluating the video's clickability, length, hook, or warning about optimizations (maximum 30 words).
        
        Format your response strictly as a JSON object:
        {{
          "title": "...",
          "description": "...",
          "tags": ["tag1", "tag2", ...],
          "review_note": "..."
        }}
        """
        try:
            url = f"{settings.CF_AI_URL.rstrip('/')}/chat/completions"
            payload = {
                "model": "hermes",
                "messages": [
                    {"role": "system", "content": "You are a professional YouTube SEO and growth strategist named Hermes."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            }
            resp = httpx.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15.0
            )
            if resp.status_code == 200:
                ai_data = resp.json()
                if "choices" in ai_data and len(ai_data["choices"]) > 0:
                    text = ai_data["choices"][0]["message"]["content"]
                    start_idx = text.find("{")
                    end_idx = text.rfind("}")
                    if start_idx != -1 and end_idx != -1:
                        parsed = json.loads(text[start_idx:end_idx+1])
                        return {
                            "title": parsed.get("title", fallback["title"])[:100],
                            "description": parsed.get("description", fallback["description"]),
                            "tags": parsed.get("tags", fallback["tags"])[:15],
                            "confidence_score": Decimal("95.00"),
                            "ai_review_note": f"Hermes: {parsed.get('review_note', 'Metadata dioptimasi oleh AI.')}"
                        }
        except Exception as e:
            logger.warning("cf_ai_metadata_draft_generation_failed", error=str(e))
            
        return fallback

