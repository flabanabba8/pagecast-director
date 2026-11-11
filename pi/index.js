import { fileURLToPath } from 'node:url'

// Pi connects these tools; its selected model and existing authentication stay in Pi.
export default function pagecastDirector(pi) {
  pi.registerMcpServer('pagecast-director', {
    command: process.env.PAGECAST_PYTHON || 'python3',
    args: [fileURLToPath(new URL('../server.py', import.meta.url))],
  })
}
