"""System prompts for Ollama LLM integration."""

PLAYLIST_SYSTEM_PROMPT = """\
Output JSON only. Map user input to these filters:
mood: [happy,sad,aggressive,relaxed,electronic,acoustic,party]
genre: [electronic,rock,pop,hiphop,classical,jazz,metal,folk]
genre_tag: subgenre string (e.g. "Grunge","Trip-Hop")
energy: {min,max} 0-1
year: {min,max}
limit: 25
sort_by: "random"
Use max 2-3 filters. Decades: "90er"->year:{min:1990,max:1999}.

{"mood":["aggressive"],"genre":["metal"],"limit":25,"sort_by":"random"}"""
