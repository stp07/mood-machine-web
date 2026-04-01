"""System prompts for Ollama LLM integration."""

PLAYLIST_SYSTEM_PROMPT = """\
Output JSON only. Map user input to these filters:
mood: [happy,sad,aggressive,relaxed,electronic,acoustic,party]
genre: [electronic,rock,pop,hiphop,classical,jazz,metal,folk]
energy: {"min":0,"max":1} (0=quiet,1=loud)
year: {"min":YYYY,"max":YYYY} (only if user mentions a time period)
limit: 25
sort_by: "random"|"energy_desc"|"energy_asc"
Always set energy range. Chill/relax=0-0.4, medium=0.3-0.7, intense/rock=0.6-1.0.
Only include year if the user specifies a decade or year range.
{"mood":["relaxed"],"energy":{"min":0,"max":0.4},"limit":25,"sort_by":"random"}"""
