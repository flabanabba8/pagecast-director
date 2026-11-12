"""Find out which speech resources this computer and this Hermes profile really have, and choose one.

Nothing here sends text anywhere, spends money or reveals a credential: discovery looks for installed
programs, loopback servers that answer, settings that are filled in, and whether a secret EXISTS (a yes/no,
never its value). The plugin then builds its narration route from what was found instead of assuming one
vendor.

Policy (the reason this module exists):
- The plugin NEVER picks a speech engine for the user. It lists what it found, with plain notes on what each
  one is (local or online, free or paid), and ASKS which one to use. The answer is saved in the profile.
- Only the route the user chose is used. If it stops being available the plugin says so and asks again.
- Nothing is silently swapped: callers must report which route actually ran.
This file is shared verbatim by creator-studio and pagecast-director; keep the two copies identical.
"""
import json
import os
import shutil
import subprocess
import sys
from urllib.request import ProxyHandler, build_opener

LOOPBACK_PORTS = (8000, 8880, 5002, 8020, 8080)
# Preference among FREE ready routes (best sounding first). A loopback neural server beats a command-line voice.
FREE_ORDER = ('server', 'piper', 'say', 'sapi', 'espeak-ng', 'flite')
SYSTEM_TOOLS = ('piper', 'say', 'sapi', 'espeak-ng', 'flite')
DEFAULT_VOICE = {'piper': 'default', 'say': 'Samantha', 'sapi': 'default', 'espeak-ng': 'en-us', 'flite': 'rms'}


def read_secret(name):
    """Value of a secret from Hermes's profile scope (falls back to the environment); '' when absent.
    Callers must never log or return it."""
    try:
        from agent.secret_scope import get_secret
        value = get_secret(name)
    except Exception:
        value = os.environ.get(name)
    return value.strip() if isinstance(value, str) else ''


def _truthy(value):
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _opener():
    from urllib.request import HTTPRedirectHandler

    class Stop(HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    return build_opener(ProxyHandler({}), Stop)


def _is_loopback_http(url):
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(url)
        return parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost', '::1') and not parts.username and not parts.password
    except ValueError:
        return False


def _server_models(url, timeout=1.0):
    if not _is_loopback_http(url):
        return None
    try:
        with _opener().open(url.rstrip('/') + '/v1/models', timeout=timeout) as response:
            data = json.loads(response.read(200000))
        return [m.get('id') for m in data.get('data', []) if isinstance(m, dict) and m.get('id')][:5]
    except Exception:
        return None


def find_servers(extra_urls=(), probe=True):
    """Loopback OpenAI-style speech servers that answer /v1/models. Only http on this computer is ever probed."""
    urls = [u for u in extra_urls if isinstance(u, str) and u]
    urls += ['http://127.0.0.1:%d' % p for p in LOOPBACK_PORTS]
    seen, found = set(), []
    for url in urls:
        key = url.rstrip('/').replace('//localhost', '//127.0.0.1')
        if key in seen or not _is_loopback_http(key):
            continue
        seen.add(key)
        models = _server_models(key) if probe else None
        if models is not None:
            found.append({'url': key, 'models': models})
    return found


def system_tools(which=shutil.which, platform=None, piper_model=''):
    """Speech programs already installed. 'piper' also needs a voice model file; 'sapi' is Windows' built-in voice."""
    platform = platform or sys.platform
    out = {}
    if which('espeak-ng') or which('espeak'):
        out['espeak-ng'] = which('espeak-ng') or which('espeak')
    if which('flite'):
        out['flite'] = which('flite')
    if platform == 'darwin' and which('say'):
        out['say'] = which('say')
    if platform.startswith('win') and (which('powershell') or which('pwsh')):
        out['sapi'] = which('powershell') or which('pwsh')
    if which('piper') and piper_model and os.path.isfile(os.path.expanduser(piper_model)):
        out['piper'] = which('piper')
    return out


def discover(settings=None, secret_present=None, which=shutil.which, platform=None, probe=True, hosted=('gemini', 'elevenlabs', 'inworld')):
    """Return {'backends': [...], 'free_ready': [...], 'advice': str}. Nothing is ranked or recommended.

    hosted: the cloud providers this plugin can actually drive (others are never reported as usable).
    settings: the plugin's settings dict. secret_present(name) -> bool: whether a named secret exists (value never read).
    """
    s = settings or {}
    has = secret_present or (lambda name: bool(os.environ.get(name)))
    backends = []
    for tool, path in system_tools(which, platform, str(s.get('piper_model', ''))).items():
        backends.append({'id': 'system:' + tool, 'kind': 'system', 'tool': tool, 'ready': True, 'free': True, 'local': True,
                         'detail': 'installed program on this computer; nothing leaves it'})
    if 'piper' not in {b['tool'] for b in backends} and which('piper'):
        backends.append({'id': 'system:piper', 'kind': 'system', 'tool': 'piper', 'ready': False, 'free': True, 'local': True,
                         'detail': 'installed, but needs a voice model file: set piper_model to a local .onnx path'})
    for server in find_servers([s.get('speech_http_url', ''), s.get('higgs_url', '')], probe):
        backends.append({'id': 'server:' + server['url'], 'kind': 'server', 'ready': True, 'free': True, 'local': True,
                         'models': server['models'], 'detail': 'speech server answering on this computer'})
    gem_key = has('GEMINI_API_KEY')
    gem_project = bool(str(s.get('gemini_project', '')).strip())
    if gem_key and 'gemini' in hosted:
        backends.append({'id': 'gemini:developer', 'kind': 'hosted', 'ready': True, 'free': False, 'local': False,
                         'detail': 'Gemini speech with your API key; text is sent to Google and may use quota or billing'})
    if gem_project and 'gemini' in hosted:
        backends.append({'id': 'gemini:vertex', 'kind': 'hosted', 'ready': True, 'free': False, 'local': False,
                         'detail': 'Gemini speech on Vertex AI in your Cloud project; needs the Hermes Google sign-in; billed to the project'})
    for name, env in (('elevenlabs', 'ELEVENLABS_API_KEY'), ('inworld', 'INWORLD_API_KEY')):
        if has(env) and name in hosted:
            backends.append({'id': name, 'kind': 'hosted', 'ready': True, 'free': False, 'local': False,
                             'detail': 'hosted speech with your account key; text is sent to the provider and uses account credits'})
    if str(s.get('host_tts_tool', '')).strip() and str(s.get('host_tts_backend_id', '')).strip():
        backends.append({'id': 'host:' + str(s['host_tts_tool']), 'kind': 'host', 'ready': True, 'free': None, 'local': None,
                         'detail': 'a speech tool you selected in Hermes; Hermes owns its model, sign-in and approvals; cost unknown to this plugin'})
    backends = filter_report({'backends': backends}, s)['backends']
    free_ready = [b for b in backends if b['ready'] and b['free'] and b.get('local')]
    return {'backends': backends, 'free_ready': [b['id'] for b in free_ready],
            'advice': advice(backends)}


def ready_options(report):
    """The routes the user can pick from, in a stable order, each with plain words about where text goes and cost."""
    out = []
    for b in report['backends']:
        if not b['ready']:
            continue
        where = 'stays on this computer' if b.get('local') else 'text is sent to an online service' if b.get('local') is False else 'handled by a Hermes tool (where text goes depends on that tool)'
        cost = 'free' if b.get('free') else 'may cost money' if b.get('free') is False else 'cost unknown'
        out.append({'id': b['id'], 'what': b['detail'], 'where_text_goes': where, 'cost': cost})
    return sorted(out, key=lambda o: o['id'])


def chosen(report, profile):
    """The backend the USER picked in the interview, if it is still available; otherwise None. Never a guess."""
    route = (profile or {}).get('route')
    if not route:
        return None
    for b in report['backends']:
        if b['ready'] and b['id'] == route:
            return b
    return None


def advice(backends):
    ready = [b for b in backends if b['ready']]
    if not ready:
        return ('No speech route was found. Easiest free fix: install espeak-ng (or flite) with your package manager, or start a local '
                'speech server, or set a Gemini/ElevenLabs/Inworld key in this plugin\'s Hermes settings. Nothing was sent or spent.')
    return 'Found %d speech route(s): %s. The user chooses which one to use; nothing is picked for them.' % (len(ready), ', '.join(b['id'] for b in ready))


def resolve(settings, requested, report=None):
    """Turn an explicitly named backend into a ready backend, or raise. 'auto' does not exist: ask the user instead."""
    report = report or discover(settings)
    if requested in (None, '', 'auto', 'chosen'):
        raise ValueError('No speech route has been chosen. Ask the user which one to use (speech setup tool). ' + report['advice'])
    matches = [b for b in report['backends'] if b['ready'] and (b['id'] == requested or b['id'].split(':')[0] == requested or b.get('tool') == requested)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError('"%s" matches several routes (%s); name one exactly.' % (requested, ', '.join(b['id'] for b in matches)))
    raise ValueError('The speech route "%s" is not available on this computer. %s' % (requested, report['advice']))


def synthesize_system(tool, text, voice, out_path, which=shutil.which, run=subprocess.run, piper_model='', timeout=120):
    """Speak text into a WAV file with an installed program. Arguments are passed as a list (no shell). Returns out_path."""
    voice = voice or DEFAULT_VOICE.get(tool, 'default')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Nothing to speak')
    if any(ord(c) < 32 and c not in '\n\t' for c in text):
        raise ValueError('Unsupported control text in speech')
    if not isinstance(voice, str) or not voice[:1].isalnum() or len(voice) > 128 or not all(c.isalnum() or c in ' _.:+-' for c in voice):
        raise ValueError('Voice names use letters, digits and _ . : + - only')
    out = str(out_path)
    env = dict(os.environ)
    if tool == 'espeak-ng':
        exe = which('espeak-ng') or which('espeak')
        argv = [exe, '-v', voice, '-w', out, '--stdin']
        stdin = text
    elif tool == 'flite':
        argv = [which('flite'), '-voice', voice, '-o', out, '-t', text]
        stdin = None
    elif tool == 'say':
        argv = [which('say'), '-v', voice, '-o', out, '--file-format=WAVE', '--data-format=LEI16@22050', '-f', '-']
        stdin = text
    elif tool == 'sapi':
        env['HERMES_SPEECH_TEXT'] = text
        env['HERMES_SPEECH_OUT'] = out
        env['HERMES_SPEECH_VOICE'] = '' if voice == 'default' else voice
        script = ('Add-Type -AssemblyName System.Speech;$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;'
                  'if($env:HERMES_SPEECH_VOICE){$s.SelectVoice($env:HERMES_SPEECH_VOICE)};'
                  '$s.SetOutputToWaveFile($env:HERMES_SPEECH_OUT);$s.Speak($env:HERMES_SPEECH_TEXT);$s.Dispose()')
        argv = [which('powershell') or which('pwsh'), '-NoProfile', '-NonInteractive', '-Command', script]
        stdin = None
    elif tool == 'piper':
        model = os.path.expanduser(piper_model)
        if not model or not os.path.isfile(model):
            raise ValueError('Piper needs piper_model set to a local voice model (.onnx)')
        argv = [which('piper'), '--model', model, '--output_file', out]
        stdin = text
    else:
        raise ValueError('Unknown system speech tool')
    if not argv[0]:
        raise ValueError('The speech program %s is no longer installed' % tool)
    result = run(argv, input=stdin, text=True, capture_output=True, env=env, timeout=timeout, check=False)
    if result.returncode != 0 or not os.path.isfile(out) or os.path.getsize(out) < 100:
        raise RuntimeError('%s did not produce audio (exit %s); nothing was sent anywhere' % (tool, result.returncode))
    return out


def system_voices(tool, which=shutil.which, run=subprocess.run):
    """Voice names an installed program can use (best effort, bounded). Used to give speakers different voices."""
    try:
        if tool == 'flite':
            out = run([which('flite'), '-lv'], capture_output=True, text=True, timeout=10).stdout
            names = out.split(':', 1)[-1].split()
            return [n for n in names if n.replace('_', '').isalnum()][:12] or ['rms']
        if tool == 'espeak-ng':
            # base voices plus male/female variants: distinct enough to tell speakers apart
            return ['en-us+m3', 'en-us+f3', 'en-gb+m5', 'en-gb+f5', 'en-us+m7', 'en-us+f2']
        if tool == 'say':
            out = run([which('say'), '-v', '?'], capture_output=True, text=True, timeout=10).stdout
            names = [line.split('  ')[0].strip() for line in out.splitlines() if line.strip().startswith(('Samantha', 'Daniel', 'Karen', 'Moira', 'Alex', 'Fred', 'Victoria', 'Tessa'))]
            return names[:8] or ['Samantha']
    except Exception:
        pass
    return [DEFAULT_VOICE.get(tool, 'default')]


def assign_voices(tool, speakers, requested=None, which=shutil.which, run=subprocess.run):
    """One voice per speaker: the user's choice where given, else different voices from the program's own list."""
    pool = system_voices(tool, which, run)
    out, taken = {}, 0
    for speaker in speakers:
        if requested and requested.get(speaker):
            out[speaker] = requested[speaker]
        else:
            out[speaker] = pool[taken % len(pool)]
            taken += 1
    return out, len(pool) < len(speakers)


# ---------------------------------------------------------------- first-use interview
PROFILE_NAME = 'speech-profile.json'
QUESTIONS = [
    {'key': 'needs', 'ask': 'What do you want to make with spoken audio (for example video voice-overs, tutorials, a podcast, an audiobook), in which language, and roughly how much?', 'type': 'text'},
    {'key': 'quality', 'ask': 'Does the voice need to sound natural and human, or is a plain robotic voice fine for now?', 'type': 'choice', 'choices': ['natural', 'plain-ok']},
    {'key': 'allow_cloud', 'ask': 'Is it OK to send the text to be spoken to an online speech service? (Free local voices send nothing anywhere.)', 'type': 'yes/no'},
    {'key': 'allow_paid', 'ask': 'If an online service is used and it costs money, is that OK? What is the most you want to spend on one project, in US dollars?', 'type': 'yes/no plus number', 'also': 'budget_usd'},
    {'key': 'has', 'ask': 'What do you already have? Tell me which of these apply (never paste a key into chat; keys go in this plugin\'s Hermes settings): a speech server running on this computer (and its address), a Gemini API key, a Google Cloud project, an ElevenLabs key, an Inworld key, a speech tool already installed in Hermes.', 'type': 'list', 'choices': ['local_server', 'gemini_key', 'google_cloud_project', 'elevenlabs_key', 'inworld_key', 'host_speech_tool', 'nothing']},
    {'key': 'voice_notes', 'ask': 'Any voice preferences (male or female, calm or lively, accent)?', 'type': 'text'},
]
_HAS = {q for q in QUESTIONS[4]['choices']}


def profile_path(root):
    """One profile shared by all parts of a plugin: stored next to the part's own data folder."""
    from pathlib import Path
    return Path(root).parent / 'speech-profile' / PROFILE_NAME


def load_profile(root):
    try:
        data = json.loads(profile_path(root).read_text())
        return data if isinstance(data, dict) and data.get('answered') else None
    except (OSError, ValueError):
        return None


def save_profile(root, answers, ready_ids=None):
    """Validate and store the user's interview answers (no secrets: keys are only named, never stored here)."""
    if not isinstance(answers, dict):
        raise ValueError('answers must be an object with the interview keys')
    out = {'answered': True}
    needs = answers.get('needs', '')
    if not isinstance(needs, str) or not needs.strip() or len(needs) > 600:
        raise ValueError('needs: say in a sentence what you want to make (up to 600 characters)')
    out['needs'] = needs.strip()
    if answers.get('quality') not in ('natural', 'plain-ok'):
        raise ValueError('quality must be natural or plain-ok')
    out['quality'] = answers['quality']
    for key in ('allow_cloud', 'allow_paid'):
        if type(answers.get(key)) is not bool:
            raise ValueError('%s must be true or false' % key)
        out[key] = answers[key]
    if out['allow_paid'] and not out['allow_cloud']:
        raise ValueError('allow_paid needs allow_cloud: paid services are online services')
    budget = answers.get('budget_usd', 0)
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not 0 <= budget <= 100:
        raise ValueError('budget_usd must be a number from 0 to 100')
    if out['allow_paid'] and budget <= 0:
        raise ValueError('Give a per-project ceiling above 0 USD when paid use is allowed')
    out['budget_usd'] = float(budget)
    has = answers.get('has', [])
    if not isinstance(has, list) or any(h not in _HAS for h in has):
        raise ValueError('has must list only: ' + ', '.join(sorted(_HAS)))
    out['has'] = sorted(set(has))
    notes = answers.get('voice_notes', '')
    if not isinstance(notes, str) or len(notes) > 300:
        raise ValueError('voice_notes: at most 300 characters')
    out['voice_notes'] = notes.strip()
    route = answers.get('route')
    if route is not None:
        if not isinstance(route, str) or len(route) > 300:
            raise ValueError('route must be the id of one of the options you were shown')
        if ready_ids is not None and route not in ready_ids:
            raise ValueError('route "%s" is not one of the available options: %s' % (route, ', '.join(sorted(ready_ids)) or 'none'))
        if route and not out['allow_cloud'] and not (route.startswith('system:') or route.startswith('server:')):
            raise ValueError('You said nothing should be sent online, so choose a route that stays on this computer')
    out['route'] = route or None
    path = profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(out, indent=2))
    tmp.chmod(0o600)
    tmp.replace(path)
    return out


def apply_profile(settings, profile):
    """Settings as the user's answers shape them. Explicit plugin settings the user changed are not overridden
    except to make things stricter: a 'no cloud' answer always wins."""
    s = dict(settings or {})
    if not profile:
        return s
    if not profile['allow_cloud']:
        s['speech_allow_cloud'] = 'false'
    if profile['allow_paid']:
        cap = float(profile['budget_usd'])
        try:
            cap = min(cap, float(s['gemini_max_usd']))   # never raise a stricter limit the user already set
        except (KeyError, TypeError, ValueError):
            pass
        s['gemini_max_usd'] = cap
    return s


def gaps(report, profile):
    """What the user wants versus what was found: plain next steps, never a silent downgrade."""
    notes = []
    free = [b for b in report['backends'] if b['ready'] and b['free'] and b.get('local')]
    natural_free = [b for b in free if b['kind'] == 'server' or b.get('tool') in ('piper', 'say', 'sapi')]
    if profile['quality'] == 'natural' and not natural_free:
        notes.append('You asked for a natural voice, but the only free local voices found sound robotic (%s). Options: start a local neural speech server, set up Piper with a voice model, or allow an online service. Check the provider\'s pricing page before choosing a paid one.' % (', '.join(b['id'] for b in free) or 'none found'))
    if not profile['allow_cloud']:
        cloud = [b['id'] for b in report['backends'] if not b.get('local')]
        if cloud:
            notes.append('Online routes exist (%s) but you said nothing should be sent online, so they will not be used.' % ', '.join(cloud))
    claimed = {'gemini_key': 'gemini:developer', 'google_cloud_project': 'gemini:vertex', 'local_server': None}
    found_ids = {b['id'] for b in report['backends']}
    for item in profile['has']:
        want = claimed.get(item)
        if item == 'local_server' and not any(i.startswith('server:') for i in found_ids):
            notes.append('You said a speech server runs on this computer, but none answered on the usual ports. Give its address in the plugin setting speech_http_url, or start it.')
        elif want and want not in found_ids:
            notes.append('You said you have %s, but it is not set up where this plugin can see it (a key goes in the plugin\'s Hermes settings; a project in gemini_project).' % item.replace('_', ' '))
    if not report['backends']:
        notes.append(report['advice'])
    return notes


def interview(settings, root, report, answers=None):
    """First-use interview. Without answers: returns what was found, the questions, and the options to pick from.
    With answers: validates, saves (including the route the user chose) and says what is still missing.
    Sends nothing, spends nothing, and never picks a route for the user."""
    options = ready_options(filter_report(report, settings))
    if answers is not None:
        if options and not (isinstance(answers, dict) and answers.get('route')):
            raise ValueError('Ask the user which of these routes to use and pass it as route (nothing was saved): ' + ', '.join(o['id'] for o in options))
        profile = save_profile(root, answers, {o['id'] for o in options} if options else None)
        return {'state': 'saved', 'profile': profile, 'you_chose': profile['route'], 'gaps': gaps(report, profile), 'found': report['backends']}
    existing = load_profile(root)
    questions = list(QUESTIONS)
    questions.append({'key': 'route', 'ask': 'Which of these do you want to use for speech? I will use only the one you pick.', 'type': 'choice', 'choices': options})
    state = 'interview_needed' if not existing or (options and not existing.get('route')) else 'answered'
    return {'state': state, 'profile': existing, 'found': report['backends'], 'options': options, 'recommendations': recommend(hardware(), load_catalog(update_root=root), allow_cloud=not existing or existing.get('allow_cloud', True)), 'knowledge_freshness': speech_freshness(root), 'advice': report['advice'], 'questions': questions,
            'instructions_for_agent': 'Do not choose a speech engine for the user. Show them the options found on this computer in plain words (what each is, whether the text stays here or goes online, whether it is free). Then show `recommendations` as suggestions, not a decision: for online speech the suggested order (Gemini 3.8 Flash TTS for the best quality, then Inworld, then ElevenLabs) with the free allowance of each and its verified date; and for local speech the models that fit the hardware of this computer, which may need installing first (offer to help, never install without being asked). Quote free allowances and prices only with their source and date, and tell the user to re-check the link. Also read `knowledge_freshness`: if it says stale (or something is coming up), follow its offer: tell the user what may be old and ask whether they want you to research the current facts online; never research without their yes. Ask which one they want, together with the other questions, in one short message. Do not ask for or accept key values in chat. Then call the speech setup tool again with answers = {needs, quality, allow_cloud, allow_paid, budget_usd, has, voice_notes, route}. If no option exists, explain how to get one and stop. Do not start narration until the answers are saved.'}


def speech_freshness(root, today=None):
    cat = load_catalog(update_root=root)
    return freshness(cat.get('verified'), cat.get('expiries', []), cat.get('last_refresh'), today)


def apply_setup(root, report, settings, answers=None, knowledge_updates=None):
    """Shared body of every speech setup tool: optionally store user-approved research, then run the interview."""
    saved = None
    if knowledge_updates is not None:
        saved = len(save_updates(root, knowledge_updates, known_ids())['updates'])
    out = interview(settings, root, report, answers)
    if saved is not None:
        out['knowledge_updates_saved'] = len(knowledge_updates)
    return out


def known_ids():
    cat = load_catalog()
    return {r['id'] for k in ('remote', 'local', 'servers', 'other_remote_with_free_tiers') for r in cat.get(k, [])}


def filter_report(report, settings):
    """Drop online/host routes when the settings say nothing may be sent online."""
    if str((settings or {}).get('speech_allow_cloud', 'true')).lower() == 'false':
        return {**report, 'backends': [b for b in report['backends'] if b.get('local')]}
    return report


def refuse_cloud_if_forbidden(settings_or_profile, what):
    """A 'no online services' answer beats an explicit cloud choice: raise instead of sending text away."""
    forbidden = (str(settings_or_profile.get('speech_allow_cloud', 'true')).lower() == 'false') or (settings_or_profile.get('allow_cloud') is False)
    if forbidden:
        raise ValueError('You said nothing should be sent to an online service, so %s will not be used. Change your answer with the speech setup tool if that is no longer true.' % what)


# ---------------------------------------------------------------- hardware + recommendations
def hardware(run=subprocess.run, platform=None, which=shutil.which, read_text=None):
    """Numbers only about THIS computer: operating system, CPU threads, RAM, GPUs with memory, Apple Silicon.
    No hostname, serial number or account detail. Reads local files and runs local programs; sends nothing."""
    platform = platform or sys.platform
    def _read(path):
        with open(path) as f:
            return f.read()
    read_text = read_text or _read
    hw = {'os': 'windows' if platform.startswith('win') else 'macos' if platform == 'darwin' else 'linux',
          'cpu_threads': os.cpu_count() or 1, 'ram_gb': None, 'gpus': [], 'apple_silicon': False}

    def out(argv, timeout=15):
        try:
            r = run(argv, capture_output=True, text=True, timeout=timeout)
            return r.stdout if r.returncode == 0 else ''
        except Exception:
            return ''
    try:
        if hw['os'] == 'linux':
            for line in read_text('/proc/meminfo').splitlines():
                if line.startswith('MemTotal:'):
                    hw['ram_gb'] = round(int(line.split()[1]) / 1024 / 1024, 1)
        elif hw['os'] == 'macos':
            mem = out(['sysctl', '-n', 'hw.memsize']).strip()
            hw['ram_gb'] = round(int(mem) / 1024 ** 3, 1) if mem.isdigit() else None
            brand = out(['sysctl', '-n', 'machdep.cpu.brand_string'])
            hw['apple_silicon'] = 'Apple' in brand
        else:
            mem = out(['powershell', '-NoProfile', '-Command', '(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory']).strip()
            hw['ram_gb'] = round(int(mem) / 1024 ** 3, 1) if mem.isdigit() else None
    except Exception:
        pass
    if which('nvidia-smi'):
        text = out([which('nvidia-smi'), '--query-gpu=name,memory.total,compute_cap', '--format=csv,noheader,nounits'])
        for line in text.splitlines():
            parts = [p.strip() for p in line.split(',')]
            if len(parts) == 3 and parts[1].isdigit():
                try:
                    cc = float(parts[2])
                except ValueError:
                    cc = None
                hw['gpus'].append({'vendor': 'nvidia', 'name': parts[0], 'vram_gb': round(int(parts[1]) / 1024, 1), 'compute_capability': cc})
        if not hw['gpus']:   # older drivers do not know compute_cap
            for line in out([which('nvidia-smi'), '--query-gpu=name,memory.total', '--format=csv,noheader,nounits']).splitlines():
                name, _, mem = line.rpartition(',')
                if name and mem.strip().isdigit():
                    hw['gpus'].append({'vendor': 'nvidia', 'name': name.strip(), 'vram_gb': round(int(mem) / 1024, 1), 'compute_capability': None})
    if which('rocm-smi') and not hw['gpus']:
        try:
            data = json.loads(out([which('rocm-smi'), '--showmeminfo', 'vram', '--json']) or '{}')
            for card, info in data.items():
                total = info.get('VRAM Total Memory (B)')
                if total and str(total).isdigit():
                    hw['gpus'].append({'vendor': 'amd', 'name': card, 'vram_gb': round(int(total) / 1024 ** 3, 1)})
        except Exception:
            pass
    return hw


def usable_gpu_memory(hw):
    """GB a model could use: the biggest single GPU's VRAM, or on Apple Silicon about 70 percent of unified memory."""
    best = max((g['vram_gb'] for g in hw['gpus']), default=0)
    if hw['apple_silicon'] and hw['ram_gb']:
        best = max(best, round(hw['ram_gb'] * 0.7, 1))
    return best


REMOTE_ORDER = ('gemini', 'inworld', 'elevenlabs')   # the maintainers' quality order for hosted speech; a suggestion, never a choice


def load_catalog(path=None, update_root=None):
    """The shipped catalog, with the user's approved research updates laid over it when update_root is given."""
    from pathlib import Path
    path = Path(path) if path else Path(__file__).resolve().parent / 'speech_catalog.json'
    try:
        cat = json.loads(path.read_text())
    except (OSError, ValueError):
        return {'verified': None, 'remote': [], 'local': [], 'servers': [], 'expiries': []}
    if update_root is not None:
        data = load_updates(update_root)
        for key in ('remote', 'local', 'servers', 'other_remote_with_free_tiers'):
            apply_updates(cat.get(key, []), data['updates'])
        cat['last_refresh'] = data.get('last_refresh')
    return cat


def recommend(hw, catalog=None, allow_cloud=True):
    """Suggestions for the agent to SHOW the user. Remote services in the maintainers' order with their verified
    free-tier facts; local models that fit this computer's hardware, best fitting first. Never a choice."""
    cat = catalog or load_catalog()
    gpu = usable_gpu_memory(hw)
    ram = hw.get('ram_gb') or 0
    local = []
    for m in cat.get('local', []):
        if m.get('recommend') is False:
            continue
        need_gpu = m.get('min_vram_gb')
        cpu_ok = m.get('cpu_ok')
        need_ram = m.get('min_ram_gb') or 0
        if need_gpu is not None and gpu >= need_gpu and ram >= need_ram:
            fit = 'fits your GPU (%.0f GB available, needs about %s GB)' % (gpu, need_gpu)
        elif cpu_ok and ram >= need_ram:
            fit = 'runs on CPU (%s GB RAM here, needs about %s GB)%s' % (ram, need_ram or 'little', '' if not need_gpu else '; faster with a GPU')
        else:
            continue
        note = None
        mc = m.get('min_compute_capability')
        cc = max((g.get('compute_capability') or 0 for g in hw['gpus']), default=0)
        if mc and need_gpu is not None and gpu >= need_gpu and cc and cc < mc:
            note = 'Your GPU (compute capability %.1f) is older than the %.1f this model is documented for; expect a fallback mode or problems.' % (cc, mc)
        local.append({'id': m['id'], 'name': m['name'], 'fit': fit, 'gpu_note': note, 'gpu_requirements': m.get('gpu_requirements'), 'smaller_variants': m.get('smaller_variants'), 'rtf': m.get('rtf'), 'tier': m.get('tier', 9), 'license': m.get('license'), 'cloning': m.get('cloning'),
                      'commercial': m.get('commercial'), 'languages': m.get('languages'), 'vram_basis': m.get('vram_basis'), 'status': m.get('status'), 'works_with_this_plugin': ('yes: it exposes an OpenAI-style /v1/audio/speech server, which the speech-server route can use' if str(m.get('openai_endpoint', '')).startswith('yes') else 'not directly: needs a speech server or adapter first (ask the user before installing anything)' if m.get('id') not in ('espeak-ng', 'flite', 'piper') else 'yes: used directly as an installed program'), 'how_to_run': m.get('how_to_run'), 'notes': m.get('notes'), 'source': m.get('source'), 'verified': m.get('verified')})
    servers = cat.get('servers', [])
    by_id = {}
    for sv in servers:
        for mid in sv.get('models', []):
            by_id.setdefault(mid, []).append(sv)
    for m in local:
        runners = by_id.get(m['id'], [])
        m['servers_that_can_run_it'] = [{'name': sv['name'], 'install': sv.get('install'), 'openai_style_endpoint': sv.get('openai_style'), 'platforms': sv.get('platforms'), 'status': sv.get('status'), 'source': sv.get('source')} for sv in runners]
        if any(str(sv.get('openai_style', '')).startswith('yes') for sv in runners) and not m['works_with_this_plugin'].startswith('yes'):
            m['works_with_this_plugin'] = 'yes, once run behind an OpenAI-style server (%s); the user must install it first' % ', '.join(sv['name'] for sv in runners if str(sv.get('openai_style', '')).startswith('yes'))
    local.sort(key=lambda m: (m['tier'], m['name']))
    remote = []
    if allow_cloud:
        by = {r['id']: r for r in cat.get('remote', [])}
        for i, key in enumerate(REMOTE_ORDER, 1):
            if key in by:
                r = by[key]
                remote.append({'rank': i, **{k: r.get(k) for k in ('id', 'name', 'models', 'free_tier', 'paid', 'needs', 'source', 'verified', 'caveats')}})
    return {'hardware': hw, 'remote_in_suggested_order': remote, 'other_online_services_with_free_tiers': cat.get('other_remote_with_free_tiers', []) if allow_cloud else [], 'local_that_fit_this_computer': local[:12],
            'catalog_verified': cat.get('verified'),
            'note': 'Suggestions only; the user chooses. Free-tier and price facts were checked on the dates shown and change often: re-check the source link before quoting them. Nothing was downloaded or installed.'}


# ---- knowledge freshness (generic block; identical in modlab/resources.py) ----
import datetime as _dt
MAX_AGE_DAYS = 30
UPDATE_FIELDS = ('free_tier', 'paid', 'needs', 'caveats', 'models', 'min_vram_gb', 'vram_basis', 'min_ram_gb', 'license', 'commercial', 'cloning', 'languages',
                 'status', 'notes', 'openai_endpoint', 'openai_style', 'install', 'platforms', 'how_to_run', 'smaller_variants', 'gpu_requirements', 'recommend')


def _today(today=None):
    return today or _dt.date.today()


def _parse_day(text):
    try:
        return _dt.date.fromisoformat(str(text))
    except ValueError:
        return None


def freshness(verified, expiries=(), last_refresh=None, today=None, max_age_days=MAX_AGE_DAYS):
    """Is the shipped knowledge out of date? Returns {'verified', 'age_days', 'stale', 'reasons', 'coming_up', 'offer'}.
    Stale when older than max_age_days (counting the latest user-approved research refresh) or when a known deadline has passed."""
    now = _today(today)
    days = [d for d in (_parse_day(verified), _parse_day(last_refresh)) if d]
    newest = max(days) if days else None
    age = (now - newest).days if newest else None
    reasons, coming = [], []
    if age is None:
        reasons.append('the knowledge has no verification date')
    elif age > max_age_days:
        reasons.append('it was last checked %d days ago (checked %s; this plugin treats more than %d days as stale)' % (age, newest.isoformat(), max_age_days))
    for e in expiries:
        d = _parse_day(e.get('date'))
        if not d:
            continue
        if d <= now:
            reasons.append('a known deadline has passed (%s): %s' % (d.isoformat(), e.get('what')))
        elif (d - now).days <= max_age_days:
            coming.append('%s (%s): %s' % (d.isoformat(), '%d days away' % (d - now).days, e.get('what')))
    stale = bool(reasons)
    offer = None
    if stale or coming:
        offer = ('Some of this built-in knowledge may be out of date%s. Tell the user plainly what may have changed and ASK whether they want you to research '
                 'the current facts on the internet now, using the source links in the wiki (primary pages only). Do not research without their yes. If they say yes, '
                 'read the primary pages, then save only what you verified with the setup tool\'s knowledge_updates argument (each with its source link and date), '
                 'and tell the user what changed and what you could not verify. If they say no, carry on and say the numbers may be old.') % (' (' + '; '.join(reasons) + ')' if reasons else '')
    return {'verified': newest.isoformat() if newest else None, 'age_days': age, 'stale': stale, 'reasons': reasons, 'coming_up': coming, 'offer': offer}


def _updates_path(root):
    return profile_path(root).parent / 'knowledge-updates.json'


def load_updates(root):
    try:
        data = json.loads(_updates_path(root).read_text())
        return data if isinstance(data, dict) and isinstance(data.get('updates'), list) else {'updates': [], 'last_refresh': None}
    except (OSError, ValueError):
        return {'updates': [], 'last_refresh': None}


def save_updates(root, updates, known_ids, today=None):
    """Store research results the user approved. Each update: {id, field, value, source (https URL), date}. Nothing is trusted blindly:
    unknown ids/fields, non-https sources, future dates and oversized values are refused. Returns the stored file contents."""
    now = _today(today)
    if not isinstance(updates, list) or not 1 <= len(updates) <= 100:
        raise ValueError('knowledge_updates must be a list of 1 to 100 items')
    clean = []
    for u in updates:
        if not isinstance(u, dict) or set(u) - {'id', 'field', 'value', 'source', 'date', 'note'}:
            raise ValueError('each update needs id, field, value, source and date (note is optional)')
        if u.get('id') not in known_ids:
            raise ValueError('unknown id "%s"; use an id from the wiki tables' % u.get('id'))
        if u.get('field') not in UPDATE_FIELDS:
            raise ValueError('field "%s" cannot be updated; allowed: %s' % (u.get('field'), ', '.join(UPDATE_FIELDS)))
        value = u.get('value')
        if not (isinstance(value, (str, bool, int, float, list)) or value is None) or len(json.dumps(value)) > 1500:
            raise ValueError('value is too large or not plain data')
        src = u.get('source')
        if not isinstance(src, str) or not src.startswith('https://') or len(src) > 500:
            raise ValueError('every update needs the https source page it was verified on')
        day = _parse_day(u.get('date'))
        if not day or day > now:
            raise ValueError('every update needs the date you read the source (not in the future)')
        clean.append({'id': u['id'], 'field': u['field'], 'value': value, 'source': src, 'date': day.isoformat(), 'note': str(u.get('note', ''))[:300]})
    data = load_updates(root)
    data['updates'] = (data['updates'] + clean)[-500:]
    data['last_refresh'] = max(c['date'] for c in clean)
    path = _updates_path(root)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2))
    tmp.chmod(0o600)
    tmp.replace(path)
    return data


def apply_updates(rows, updates):
    """Overlay approved research on catalog rows (the shipped catalog file is never modified). Later updates win."""
    by = {r['id']: r for r in rows}
    for u in updates:
        r = by.get(u['id'])
        if r is not None:
            r[u['field']] = u['value']
            r.setdefault('updated_by_research', {})[u['field']] = {'source': u['source'], 'date': u['date']}
    return rows
# ---- end knowledge freshness ----
