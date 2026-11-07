import { act } from 'react'
import { createRoot } from 'react-dom/client'
import plugin from '../desktop/plugin.js'

export async function run(assert, document) {
  const contributions = [], calls = []
  let imported = false
  const detail = { book: { id: 'a'.repeat(32), title: 'Original scene', revision: 1 }, total: 1, next_offset: null,
    voices: { Narrator: { engine: 'flite', voice: 'rms', locked: false } }, render: null,
    usage: { requests: 0, reported_characters: 0, unknown_outcomes: 0 },
    passages: [{ id: 0, text: '“A short original line.”', speaker: 'Narrator', chapter_title: 'Chapter1', quote_id: '0.0.0' }] }
  const copy = value => JSON.parse(JSON.stringify(value))
  const ctx = { register: c => contributions.push(c), rest: async (_, { body }) => {
    calls.push(body)
    switch (body.operation) {
      case 'pagecast_books': return { books: imported ? [detail.book] : [] }
      case 'pagecast_import': imported = true; return { book_id: detail.book.id }
      case 'pagecast_book': return copy(detail)
      case 'pagecast_assign': detail.passages[0].speaker = body.arguments.speaker; detail.voices[body.arguments.speaker] = { engine: 'flite', voice: 'rms', locked: false }; return {}
      case 'pagecast_voice': detail.voices[body.arguments.speaker] = copy(body.arguments); return {}
      case 'pagecast_inworld_voices': return { voices: [{ id: 'Ashley', name: 'Ashley', language: 'en-US' }], next_page_token: '' }
      case 'pagecast_render': detail.render = { state: 'complete', done: 1, total: 1 }; return { generated: 1, reused: 0 }
      case 'pagecast_export': return { path: '/tmp/original.m4b', seconds: 2, format: 'm4b' }
      default: throw Error('Unexpected operation: ' + body.operation)
    }
  } }
  plugin.register(ctx)
  const root = createRoot(document.getElementById('root'))
  const field = (container, name) => [...container.querySelectorAll('label')].find(e => e.firstChild?.textContent === name)?.querySelector('input,textarea,select')
  const change = async (element, value) => act(async () => {
    assert.ok(element, 'Missing form field')
    const proto = element.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : element.tagName === 'INPUT' ? window.HTMLInputElement.prototype : window.HTMLSelectElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(element, value)
    element.dispatchEvent(new window.Event(element.tagName === 'SELECT' ? 'change' : 'input', { bubbles: true }))
  })
  const click = async (text, container = document) => act(async () => {
    const button = [...container.querySelectorAll('button')].find(e => e.textContent === text)
    assert.ok(button && !button.disabled, `Missing or disabled ${text}`); button.click()
  })
  try {
    await act(async () => root.render(contributions.find(c => c.area === 'routes').render()))
    await change(field(document, 'Book title'), 'Original scene')
    await change(field(document, 'Chapter text'), '“A short original line.”')
    await act(async () => document.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })))
    assert.match(document.body.textContent, /1 passage · revision 1/)
    assert.equal(calls.filter(c => c.operation === 'pagecast_render').length, 0, 'Import must not synthesize speech')
    const passage = document.querySelector('[aria-label="Passages"] article')
    await change(field(passage, 'Speaker'), 'Mina'); await click('Assign speaker', passage)
    const voice = [...document.querySelectorAll('[aria-label="Voice cast"] article')].find(e => e.querySelector('strong').textContent === 'Mina')
    await change(field(voice, 'Engine'), 'inworld')
    assert.match(voice.textContent, /account credits/)
    await click('Load Inworld voices', voice)
    assert.ok(voice.querySelector('datalist option[value=Ashley]'))
    await click('Apply voice', voice)
    const assignment = calls.find(c => c.operation === 'pagecast_voice').arguments
    assert.equal(assignment.engine, 'inworld'); assert.equal(assignment.voice, 'Ashley'); assert.equal(assignment.locked, true)
    assert.equal(calls.filter(c => c.operation === 'pagecast_render').length, 0, 'Selecting a cloud voice must not spend credits')
    await click('Render changed passages')
    assert.match(document.querySelector('[role=status]').textContent, /complete/)
    await click('Export M4B')
    assert.equal(calls.find(c => c.operation === 'pagecast_export').arguments.format, 'm4b')
    assert.match(document.body.textContent, /Export ready/)
    await change(field(document, 'Chapter text'), '')
    await change(field(document, 'Or an absolute TXT/EPUB path on the Hermes host'), '/tmp/book.epub')
    const profileToggle = field(document, 'Allow selected books inside this profile’s plugin data')
    await act(async () => profileToggle.click())
    await act(async () => document.querySelector('form').dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true })))
    assert.equal(calls.filter(c => c.operation === 'pagecast_import').at(-1).arguments.allow_profile_books, true)
  } finally { await act(async () => root.unmount()) }
  return { passed: true, checks: ['import without synthesis', 'profile book opt-in', 'speaker assignment', 'explicit Inworld choice', 'voice catalog', 'manual voice lock', 'explicit render', 'chaptered export', 'timer cleanup'] }
}
