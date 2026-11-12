"""Report which speech routes are usable right now and, for Gemini, the named voices. Read-only; no speech is generated."""
import json
from urllib.request import ProxyHandler, build_opener
from . import vertex

# Prebuilt Gemini voices: (name, gender, trait, median pitch Hz). Gender: Google Cloud "Gemini-TTS" voice options table; trait: Google Cloud
# Gemini-TTS overview "Prebuilt voices" list (both archived 2026-11-08 under docs/gemini-tts-3.8/): vendor labels, not our listening review. Pitch: our own single measurement of one neutral sentence per voice on 2026-11-10 (rough autocorrelation median; it moves 10-20 percent with the sentence), not a listening review.
GEMINI_VOICES = [('Achernar', 'female', 'soft', 196.7), ('Achird', 'male', 'friendly', 145.5), ('Algenib', 'male', 'gravelly', 138.7), ('Algieba', 'male', 'smooth', 120.0), ('Alnilam', 'male', 'firm', 150.9), ('Aoede', 'female', 'breezy', 181.8), ('Autonoe', 'female', 'bright', 198.3), ('Callirrhoe', 'female', 'easy-going', 179.1), ('Charon', 'male', 'informative', 127.3), ('Despina', 'female', 'smooth', 164.4), ('Enceladus', 'male', 'breathy', 129.7), ('Erinome', 'female', 'clear', 206.9), ('Fenrir', 'male', 'excitable', 136.4), ('Gacrux', 'female', 'mature', 158.9), ('Iapetus', 'male', 'clear', 121.2), ('Kore', 'female', 'firm', 167.8), ('Laomedeia', 'female', 'upbeat', 169.0), ('Leda', 'female', 'youthful', 195.1), ('Orus', 'male', 'firm', 136.4), ('Puck', 'male', 'upbeat', 146.3), ('Pulcherrima', 'female', 'forward', 128.3), ('Rasalgethi', 'male', 'informative', 175.2), ('Sadachbia', 'male', 'lively', 134.8), ('Sadaltager', 'male', 'knowledgeable', 121.2), ('Schedar', 'male', 'even', 142.0), ('Sulafat', 'female', 'warm', 190.5), ('Umbriel', 'male', 'easy-going', 143.7), ('Vindemiatrix', 'female', 'gentle', 150.9), ('Zephyr', 'female', 'bright', 196.7), ('Zubenelgenubi', 'male', 'casual', 117.6)]


def _higgs(settings):
    url = settings.get('higgs_url', 'http://localhost:8000')
    try:
        with build_opener(ProxyHandler({})).open(url.rstrip('/') + '/v1/models', timeout=1.5) as response:
            data = json.loads(response.read(200000))
        return {'reachable': True, 'url': url, 'models': [m.get('id') for m in data.get('data', [])][:3],
                'note': 'Higgs: needs one locked reference clip per speaker (use pagecast_voice_audition when you have no fitting sample). Without a reference every request is a different voice.'}
    except Exception:
        return {'reachable': False, 'url': url}


def _gemini(settings):
    route, model = settings.get('gemini_route', ''), settings.get('gemini_model', 'gemini-3.8-flash-tts')
    configured = route == 'vertex' and bool(settings.get('gemini_project'))
    signin = vertex.sign_in_supported() if route == 'vertex' else None
    out = {'configured': configured, 'route': route or None, 'model': model, 'project_configured': bool(settings.get('gemini_project')),
           'spend_guard_usd': settings.get('gemini_max_usd', 3), 'hermes_sign_in_supported': signin, 'sign_in': ('Hermes holds the Google sign-in; if a request reports "not signed in", run: ' + vertex.SIGN_IN) if route == 'vertex' else None}
    if configured:
        out['voices'] = [{'voice': n, 'gender': g, 'trait': t, 'median_pitch_hz': hz} for n, g, t, hz in GEMINI_VOICES]
        out['how_to_cast'] = 'Named voices are fixed: the same name sounds the same on every request, so no reference clip is needed. Give each speaker one name that fits (gender and trait from this list) and keep the three speakers median pitches at least 20 percent apart (the narrator clearly apart from the characters, e.g. a different gender or a clearly different pitch), lock it with pagecast_voice (engine gemini, voice = the name), and use it for every passage of that speaker. Gender and trait are Google\'s labels; this tool did not listen to them.'
    return out


def speech_options(settings, discovered=None):
    return {'higgs': _higgs(settings), 'gemini': _gemini(settings), 'discovered': discovered,
            'notice': 'Read-only check of what is reachable or configured. No speech was generated, no credential or project value is shown, nothing was spent.'}
