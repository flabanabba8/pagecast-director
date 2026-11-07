import { ROUTES_AREA, SIDEBAR_NAV_AREA } from '@hermes/plugin-sdk'
import { createElement as h, useEffect, useId, useState } from 'react'

const field = { padding: '8px 10px', border: '1px solid var(--ui-stroke-secondary)', borderRadius: 7, background: 'var(--ui-bg-tertiary)', color: 'var(--ui-text-primary)' }
const card = { padding: 16, border: '1px solid var(--ui-stroke-secondary)', borderRadius: 12, display: 'grid', gap: 10 }
const row = { display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }
const button = (text, onClick, disabled = false, props = {}) => h('button', { style: { ...field, opacity: disabled ? 0.5 : 1 }, onClick, disabled, ...props }, text)
const label = (name, child) => h('label', { style: { display: 'grid', gap: 5 } }, name, child)

function Voice({ name, spec, bookId, call, task, reload, busy }) {
  const [engine, setEngine] = useState(spec.engine), [voice, setVoice] = useState(spec.voice)
  const [reference, setReference] = useState(spec.reference_audio || ''), [transcript, setTranscript] = useState(spec.reference_text || '')
  const [locked, setLocked] = useState(spec.locked)
  const [catalog, setCatalog] = useState([]), [nextPage, setNextPage] = useState('')
  const voiceListId = useId()
  useEffect(() => { setEngine(spec.engine); setVoice(spec.voice); setLocked(spec.locked); setReference(spec.reference_audio || ''); setTranscript(spec.reference_text || '') }, [spec.engine, spec.voice, spec.locked, spec.reference_audio, spec.reference_text])
  return h('article', { style: card }, h('strong', null, name),
    h('div', { style: row }, label('Engine', h('select', { style: field, value: engine, disabled: busy, onChange: e => { setEngine(e.target.value); setVoice(e.target.value === 'flite' ? 'rms' : e.target.value === 'inworld' ? 'Ashley' : 'default'); setLocked(true) } },
      h('option', { value: 'flite' }, 'Flite · local English'), h('option', { value: 'higgs' }, 'Higgs TTS 3 · local server'), h('option', { value: 'inworld' }, 'Inworld · cloud credits'))),
      label('Voice', engine === 'flite'
        ? h('select', { style: field, value: voice, disabled: busy, onChange: e => { setVoice(e.target.value); setLocked(true) } }, ...['rms', 'slt', 'awb', 'kal16', 'kal'].map(v => h('option', { key: v, value: v }, v.toUpperCase())))
        : h('input', { style: field, value: voice, list: engine === 'inworld' ? voiceListId : undefined, disabled: busy, onChange: e => { setVoice(e.target.value); setLocked(true) } }))),
    engine === 'inworld' && h('div', null,
      h('p', null, 'Speech text and the selected voice ID are sent to Inworld. Uses your configured API credential and account credits.'),
      h('datalist', { id: voiceListId }, ...catalog.map(v => h('option', { key: v.id, value: v.id }, v.name + (v.language ? ' · ' + v.language : '')))),
      button(catalog.length && nextPage ? 'More Inworld voices' : 'Load Inworld voices', () => task(async () => {
        const r = await call('pagecast_inworld_voices', { page_token: nextPage }); setCatalog(old => [...new Map([...old, ...r.voices].map(v => [v.id, v])).values()]); setNextPage(r.next_page_token)
      }), busy), h('p', null, 'If the voice list is unavailable, enter a voice ID your account can use directly (for example, Ashley).')),
    engine === 'higgs' && h('details', null, h('summary', null, 'Voice reference'),
      label('Reference WAV on the Hermes host', h('input', { style: field, value: reference, onChange: e => { setReference(e.target.value); setLocked(true) }, disabled: busy })),
      label('Reference transcript', h('textarea', { style: field, value: transcript, onChange: e => { setTranscript(e.target.value); setLocked(true) }, maxLength: 2000, disabled: busy }))),
    h('label', null, h('input', { type: 'checkbox', checked: locked, disabled: busy, onChange: e => setLocked(e.target.checked) }), ' Lock this voice'),
    button('Apply voice', () => task(async () => {
      await call('pagecast_voice', { book_id: bookId, speaker: name, engine, voice, reference_audio: engine === 'higgs' ? reference : '', reference_text: engine === 'higgs' ? transcript : '', locked, replace_locked: true }); await reload()
    }), busy))
}

function Passage({ passage, bookId, call, task, reload, busy }) {
  const [text, setText] = useState(passage.text), [speaker, setSpeaker] = useState(passage.speaker)
  useEffect(() => { setText(passage.text); setSpeaker(passage.speaker) }, [passage.text, passage.speaker])
  return h('article', { style: card }, h('div', { style: row }, h('strong', null, `Passage ${passage.id}`),
    h('span', null, passage.quote_id ? 'Quotation' : 'Narration'), h('span', null, passage.chapter_title)),
    label('Passage text', h('textarea', { style: { ...field, width: '100%', minHeight: 80 }, value: text, maxLength: 350, disabled: busy, onChange: e => setText(e.target.value) })),
    h('div', { style: row }, button('Save text', () => task(async () => { await call('pagecast_edit', { book_id: bookId, passage_id: passage.id, text }); await reload() }), busy || text === passage.text),
      label('Speaker', h('input', { style: field, value: speaker, maxLength: 80, disabled: busy, onChange: e => setSpeaker(e.target.value) })),
      button('Assign speaker', () => task(async () => { await call('pagecast_assign', { book_id: bookId, passage_ids: [passage.id], speaker }); await reload() }), busy || speaker === passage.speaker),
      button('Preview rendered audio', () => task(() => call('pagecast_preview', { book_id: bookId, passage_id: passage.id })), busy),
      button('Request new take', () => task(async () => { await call('pagecast_retry', { book_id: bookId, passage_ids: [passage.id] }); await reload() }), busy)))
}

function PageCast({ ctx }) {
  const [library, setLibrary] = useState([]), [bookId, setBookId] = useState(''), [detail, setDetail] = useState(null)
  const [title, setTitle] = useState(''), [text, setText] = useState(''), [sourcePath, setSourcePath] = useState('')
  const [allowProfileBooks, setAllowProfileBooks] = useState(false)
  const [offset, setOffset] = useState(0), [busy, setBusy] = useState(false), [rendering, setRendering] = useState(false)
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [exported, setExported] = useState(null)
  const call = (operation, args = {}) => ctx.rest('/action', { method: 'POST', body: { operation, arguments: args }, timeoutMs: 180000 })
  const task = async fn => { setBusy(true); setError(''); try { await fn() } catch (e) { setError(String(e.message || e)) } finally { setBusy(false) } }
  const reload = async (id = bookId, at = offset) => { if (id) setDetail(await call('pagecast_book', { book_id: id, offset: at, limit: 20 })) }
  useEffect(() => {
    let active = true
    call('pagecast_books').then(r => active && setLibrary(r.books)).catch(e => active && setError(String(e.message || e)))
    return () => { active = false }
  }, [ctx])
  useEffect(() => {
    if (!bookId || !(rendering || detail?.render?.state === 'rendering')) return
    let active = true
    const timer = setInterval(async () => { try { const r = await call('pagecast_book', { book_id: bookId, offset, limit: 20 }); if (active) setDetail(r) } catch (e) { if (active) setError(String(e.message || e)) } }, 2000)
    return () => { active = false; clearInterval(timer) }
  }, [ctx, bookId, offset, rendering, detail?.render?.state])
  const choose = id => task(async () => { setBookId(id); setOffset(0); setExported(null); await reload(id, 0) })
  const render = () => task(async () => {
    setRendering(true); setNotice('')
    try { const r = await call('pagecast_render', { book_id: bookId, max_segments: 20 }); setNotice(`${r.generated} new passages · ${r.reused} cached passages reused`) }
    finally { setRendering(false); await reload() }
  })
  return h('main', { style: { maxWidth: 1100, padding: 28, margin: 'auto', display: 'grid', gap: 20, color: 'var(--ui-text-primary)' } },
    h('header', null, h('h1', { style: { fontSize: 28, fontWeight: 700 } }, 'PageCast Director'), h('p', null, 'Cast the voices. Edit the lines. Keep the audio that already works.')),
    error && h('div', { role: 'alert', style: card }, error),
    h('section', { style: card, 'aria-label': 'Book library' }, h('h2', null, 'Library'),
      h('div', { style: row }, ...library.map(book => button(book.title, () => choose(book.id), busy, { key: book.id })))),
    h('details', { open: !bookId }, h('summary', null, 'Import a chapter or book'), h('form', { style: card, onSubmit: e => { e.preventDefault(); task(async () => {
      const args = { title: title || undefined, ...(sourcePath.trim() ? { source_path: sourcePath.trim(), allow_profile_books: allowProfileBooks } : { text }) }
      const imported = await call('pagecast_import', args); setLibrary((await call('pagecast_books')).books); setBookId(imported.book_id); setOffset(0); setExported(null); await reload(imported.book_id, 0)
    }) } }, label('Book title', h('input', { style: field, value: title, maxLength: 200, disabled: busy, onChange: e => setTitle(e.target.value) })),
      label('Chapter text', h('textarea', { style: { ...field, minHeight: 100 }, value: text, disabled: busy || !!sourcePath, maxLength: 1000000, onChange: e => setText(e.target.value) })),
      label('Or an absolute TXT/EPUB path on the Hermes host', h('input', { style: field, value: sourcePath, disabled: busy || !!text, onChange: e => setSourcePath(e.target.value) })),
      label('Allow selected books inside this profile’s plugin data', h('input', { type: 'checkbox', checked: allowProfileBooks, disabled: busy || !sourcePath.trim(), onChange: e => setAllowProfileBooks(e.target.checked) })),
      button('Import editable copy', undefined, busy || (!text.trim() && !sourcePath.trim()), { type: 'submit' }))),
    detail && h('section', { style: { display: 'grid', gap: 20 }, 'aria-label': 'Book editor' },
      h('div', { style: card }, h('h2', null, detail.book.title), h('p', null, `${detail.total} ${detail.total === 1 ? 'passage' : 'passages'} · revision ${detail.book.revision}`),
        h('p', { role: 'status' }, detail.render ? `${detail.render.state} · last run ${detail.render.done}/${detail.render.total}` : 'Ready to cast and render'),
        detail.usage?.requests > 0 && h('p', null, `Inworld: ${detail.usage.requests} requests · ${detail.usage.reported_characters} provider-reported characters · ${detail.usage.unknown_outcomes} unknown outcomes`),
        detail.render?.error && h('p', { role: 'alert' }, detail.render.error), notice && h('p', null, notice),
        h('div', { style: row }, button(detail.render?.state === 'partial' ? 'Resume rendering' : 'Render changed passages', render, busy),
          (rendering || detail.render?.state === 'rendering') && button('Cancel after current passage', async () => { try { await call('pagecast_cancel', { book_id: bookId }); setNotice('Cancellation requested.') } catch (e) { setError(String(e.message || e)) } }),
          button('Export M4B', () => task(async () => setExported(await call('pagecast_export', { book_id: bookId, format: 'm4b' }))), busy || detail.render?.state !== 'complete'),
          button('Export WAV', () => task(async () => setExported(await call('pagecast_export', { book_id: bookId, format: 'wav' }))), busy || detail.render?.state !== 'complete')),
        exported && h('div', null, h('p', null, `Export ready · ${exported.seconds.toFixed(1)} seconds · ${exported.format.toUpperCase()}`),
          h('details', null, h('summary', null, 'Show saved file location'), h('code', { style: { overflowWrap: 'anywhere' } }, exported.path)), exported.credit && h('p', null, exported.credit))),
      h('section', { 'aria-label': 'Voice cast', style: { display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))' } },
        ...Object.entries(detail.voices).map(([name, spec]) => h(Voice, { key: bookId + name, name, spec, bookId, call, task, reload, busy }))),
      h('section', { 'aria-label': 'Passages', style: { display: 'grid', gap: 12 } }, ...detail.passages.map(passage => h(Passage, { key: bookId + '/' + passage.id, passage, bookId, call, task, reload, busy }))),
      h('div', { style: row }, button('Previous passages', () => task(async () => { const next = Math.max(0, offset - 20); setOffset(next); await reload(bookId, next) }), busy || !offset),
        button('Next passages', () => task(async () => { const next = detail.next_offset; setOffset(next); await reload(bookId, next) }), busy || detail.next_offset == null))))
}

export default { id: 'pagecast-director', name: 'PageCast Director', register(ctx) {
  ctx.register({ id: 'page', area: ROUTES_AREA, data: { path: '/pagecast-director' }, render: () => h(PageCast, { ctx }) })
  ctx.register({ id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: '/pagecast-director', label: 'PageCast Director', codicon: 'book' } })
} }
