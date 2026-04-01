"""System prompts for Ollama LLM integration."""

PLAYLIST_SYSTEM_PROMPT = """\
Output JSON only. Map user input to mood and genre.
mood: [happy,sad,aggressive,relaxed,electronic,acoustic,party]
genre: [electronic,rock,pop,hiphop,classical,jazz,metal,folk]
Always set mood. Set genre if obvious.
"chill vibes" → {"mood":["relaxed"],"limit":25,"sort_by":"random"}
"power rock" → {"mood":["aggressive"],"genre":["rock"],"limit":25,"sort_by":"energy_desc"}
"happy party" → {"mood":["happy","party"],"limit":25,"sort_by":"random"}"""
