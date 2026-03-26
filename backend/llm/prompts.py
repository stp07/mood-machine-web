"""System prompts for Ollama LLM integration."""

PLAYLIST_SYSTEM_PROMPT = """\
Output JSON only. Map user input to these filters:
mood: [happy,sad,aggressive,relaxed,electronic,acoustic,party]
genre: [electronic,rock,pop,hiphop,classical,jazz,metal,folk]
energy: {"min":0,"max":1}
year: {"min":1990,"max":1999}
limit: 25
sort_by: "random"
Use max 2-3 filters. Example:
{"mood":["aggressive"],"genre":["rock"],"energy":{"min":0.6,"max":1.0},"limit":25,"sort_by":"random"}"""
