"""Selected host speech-tool adapter. No model/provider/auth store or fallback."""
import io
import json
import os
from pathlib import Path
import re
import stat
import wave

MAX_AUDIO=32*1024*1024
PRIVATE={'.ssh','.aws','.azure','.codex','.claude','.gnupg','.config','.docker','.kube','.pki'}
class SpeechRefused(RuntimeError): pass

def binding(settings):
    tool=settings.get('host_tts_tool','');backend=settings.get('host_tts_backend_id','')
    args=settings.get('host_tts_arguments',{})
    if isinstance(args,str):
        try:args=json.loads(args)
        except ValueError:raise ValueError('Host speech arguments must be a JSON object') from None
    if not isinstance(tool,str) or not re.fullmatch(r'[A-Za-z0-9_:/.-]{1,120}',tool): raise ValueError('Select an available host speech tool explicitly')
    if not isinstance(backend,str) or not backend.strip() or len(backend)>300: raise ValueError('Set host_tts_backend_id to the selected provider/runtime/model revision for cache identity')
    if not isinstance(args,dict) or len(json.dumps(args,allow_nan=False))>8000 or '{text}' not in json.dumps(args): raise ValueError('Configure bounded host speech tool arguments containing {text}')
    def credentials(value):
        if isinstance(value,dict):return any(str(k).casefold() in {'api_key','password','secret','authorization','access_token','refresh_token'} or credentials(v) for k,v in value.items())
        if isinstance(value,list):return any(credentials(v) for v in value)
        return False
    if credentials(args):raise ValueError('Host tool credentials belong in its Hermes settings, not speech arguments')
    field=settings.get('host_tts_audio_field','path')
    if not isinstance(field,str) or not re.fullmatch(r'[A-Za-z0-9_.]{1,120}',field):raise ValueError('Choose the returned local audio path field')
    return {'tool':tool,'backend_id':backend,'arguments':args,'model':settings.get('host_tts_model',''),'audio_field':field}

def replace(value,values):
    if isinstance(value,str):
        return re.sub(r'\{(text|voice|model)\}',lambda m:values[m.group(1)],value)
    if isinstance(value,list):return [replace(x,values) for x in value]
    if isinstance(value,dict):return {k:replace(v,values) for k,v in value.items()}
    return value

def synthesize(settings,dispatch,text,voice,data_root,observe=None):
    selected=binding(settings)
    if not callable(dispatch):raise ValueError('Selected host speech tool needs an active agent context; no provider fallback was made')
    values={'text':text,'voice':voice,'model':str(selected['model'])}
    args=replace(selected['arguments'],values)
    # All arguments are structured data; text never becomes a shell expression.
    event=observe or (lambda *_:None)
    metadata={'model_id':str(selected['model'] or selected['backend_id']),'backend_id':selected['backend_id'],'tool':selected['tool'],'reported_units':None}
    event('pending',metadata)
    try:
        result=dispatch(selected['tool'],args)
        if isinstance(result,str):result=json.loads(result)
        if not isinstance(result,dict):raise ValueError('Speech tool must return structured JSON with a local WAV path')
        if result.get('status') in ('denied','blocked','refused','cancelled'):
            event('rejected',metadata);raise SpeechRefused('Host speech tool refused or cancelled the request; approvals were preserved')
        if result.get('error') or result.get('success')is False:raise ValueError('Selected speech tool reported failure')
        path=result
        for field in selected['audio_field'].split('.'):path=path[int(field)] if isinstance(path,list) and field.isdigit() else path[field]
        if not isinstance(path,str):raise ValueError('Speech output path is not a string')
        raw=Path(path).expanduser()
        if raw.is_symlink() or any(p.casefold() in PRIVATE for p in raw.parts):raise ValueError('Speech tool returned a private-configuration or symlink path')
        raw=raw.resolve(strict=True)
        if any(p.casefold() in PRIVATE for p in raw.parts):raise ValueError('Speech output resolves into private configuration')
        if '.hermes' in [p.casefold() for p in raw.parts] and not raw.is_relative_to(Path(data_root).resolve().parent):raise ValueError('Speech output must be media in the active profile plugin data, not configuration')
        fd=os.open(raw,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(fd,'rb') as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_AUDIO:raise ValueError('Selected speech output is not a bounded regular WAV')
            data=stream.read(MAX_AUDIO+1);after=os.fstat(stream.fileno())
        identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
        if len(data)>MAX_AUDIO or identity(before)!=identity(after) or identity(after)!=identity(raw.stat()):raise ValueError('Speech output changed while reading')
        with wave.open(io.BytesIO(data)) as wav:
            if wav.getnframes()<=0 or wav.getcomptype()!='NONE' or wav.getnframes()*wav.getnchannels()*wav.getsampwidth()>len(data):raise ValueError('Host speech output needs nonempty complete PCM WAV; adapt/convert another format explicitly')
        credit=result.get('credit',settings.get('host_tts_credit',''))
        if isinstance(credit,str) and len(credit)<=2000:metadata['credit']=credit
        event('received',metadata)
        return data,metadata
    except SpeechRefused: raise
    except Exception:
        event('unknown',metadata)
        raise RuntimeError('Selected speech tool did not produce a stable bounded PCM WAV; inspect its output contract. No retry/fallback made.') from None
