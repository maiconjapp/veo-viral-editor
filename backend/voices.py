# Catalogue of Edge-TTS neural voices exposed to the UI.
# Curated across EN / PT-BR / ES for a 35-50 DIY / lifestyle audience.

VOICES = [
    # English
    {"id": "en-US-AndrewNeural",       "name": "Andrew",       "lang": "en", "gender": "male",   "style": "Warm, confident, authentic"},
    {"id": "en-US-BrianNeural",        "name": "Brian",        "lang": "en", "gender": "male",   "style": "Approachable, casual, sincere"},
    {"id": "en-US-ChristopherNeural",  "name": "Christopher",  "lang": "en", "gender": "male",   "style": "Reliable, authoritative"},
    {"id": "en-US-GuyNeural",          "name": "Guy",          "lang": "en", "gender": "male",   "style": "Passionate, energetic"},
    {"id": "en-US-AriaNeural",         "name": "Aria",         "lang": "en", "gender": "female", "style": "Natural, positive"},
    {"id": "en-US-JennyNeural",        "name": "Jenny",        "lang": "en", "gender": "female", "style": "Friendly, considerate"},
    # Portuguese (Brazil)
    {"id": "pt-BR-AntonioNeural",      "name": "Antônio",      "lang": "pt", "gender": "male",   "style": "Confiante, envolvente"},
    {"id": "pt-BR-FranciscaNeural",    "name": "Francisca",    "lang": "pt", "gender": "female", "style": "Calorosa, clara"},
    # Spanish (Latam)
    {"id": "es-MX-JorgeNeural",        "name": "Jorge",        "lang": "es", "gender": "male",   "style": "Seguro, persuasivo"},
    {"id": "es-MX-DaliaNeural",        "name": "Dalia",        "lang": "es", "gender": "female", "style": "Natural, expresiva"},
]

LANGUAGES = [
    {"id": "en", "name": "English"},
    {"id": "pt", "name": "Português (BR)"},
    {"id": "es", "name": "Español"},
]


def get_voice(voice_id: str):
    for v in VOICES:
        if v["id"] == voice_id:
            return v
    return None
