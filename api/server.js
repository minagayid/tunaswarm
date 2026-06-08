const http = require('http')
const fs = require('fs')
const path = require('path')
const { execFileSync, spawn } = require('child_process')

const ROOT = path.resolve(__dirname, '..')
const DATA_DIR = path.join(ROOT, 'data')
const DB_WORKFLOW = path.join(DATA_DIR, 'workflow.db')
const DB_TRACKING = path.join(DATA_DIR, 'tracking.db')
const DB_ALLOCATION = path.join(DATA_DIR, 'allocation.db')
const README_PATH = path.join(ROOT, 'README.md')
const PORT = 4123
const HOST = '127.0.0.1'

function sqlExec(dbPath, sql, params = []) {
  const p = spawn('sqlite3', [dbPath, sql, ...params], { encoding: 'utf8' })
  let out = ''
  p.stdout.on('data', d => { out += d })
  p.stderr.on('data', d => { console.error(d.toString()) })
  return new Promise((resolve, reject) => {
    p.on('close', code => {
      if (code !== 0) return reject(new Error('sqlite3 exit: ' + code + ' | ' + out))
      resolve(out.trim())
    })
  })
}

function sqlExecMany(dbPath, sql) {
  execFileSync('sqlite3', [dbPath], { input: sql, encoding: 'utf8' })
}

function initDBs() {
  fs.mkdirSync(DATA_DIR, { recursive: true })
  if (!fs.existsSync(DB_WORKFLOW)) sqlExecMany(DB_WORKFLOW, fs.readFileSync(path.join(ROOT, 'orchestration', 'schema.sql'), 'utf8'))
  if (!fs.existsSync(DB_TRACKING)) sqlExecMany(DB_TRACKING, fs.readFileSync(path.join(ROOT, 'tracking', 'schema.sql'), 'utf8'))
  if (!fs.existsSync(DB_ALLOCATION)) sqlExecMany(DB_ALLOCATION, fs.readFileSync(path.join(ROOT, 'allocation', 'schema.sql'), 'utf8'))
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let b = ''
    req.on('data', c => { b += c })
    req.on('end', () => { try { resolve(JSON.parse(b || '{}')) } catch (e) { reject(e) } })
    req.on('error', reject)
  })
}

async function handler(req, res) {
  const url = new URL(req.url, 'http://' + HOST)
  const parts = url.pathname.split('/').filter(Boolean)

  if (req.method === 'OPTIONS') {
    res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,POST,PUT,OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' })
    res.end()
    return
  }

  try {
    if (parts.length === 0 || (parts.length === 1 && parts[0] === '')) {
      if (req.method === 'GET') {
        const md = fs.existsSync(README_PATH) ? fs.readFileSync(README_PATH, 'utf8') : '# AI Freelance Swarm\n'
        res.writeHead(200, { 'Content-Type': 'text/markdown; charset=utf-8' })
        return res.end(md)
      }
    }

    if (parts[0] === 'api' && parts[1] === 'health' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
      return res.end(JSON.stringify({ status: 'ok', ts: new Date().toISOString() }))
    }

    if (parts[0] === 'api' && parts[1] === 'runs') {
      const runId = parts[2]
      if (req.method === 'GET' && !runId) {
        const out = await sqlExec(DB_WORKFLOW, "SELECT id, status, current_agent, current_step, total_steps, updated_at FROM workflow_runs ORDER BY created_at DESC")
        const rows = out ? out.split('\n') : []
        const data = rows.map(r => { const c = r.split('|'); return { id: c[0], status: c[1], current_agent: c[2], current_step: +c[3], total_steps: +c[4], updated_at: c[5] } })
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
        return res.end(JSON.stringify(data))
      }
      if (req.method === 'GET' && runId) {
        const row = await sqlExec(DB_WORKFLOW, "SELECT id, status, current_agent, current_step, total_steps, created_at, updated_at, finished_at, metadata FROM workflow_runs WHERE id = ?", [runId])
        if (!row) { res.writeHead(404); return res.end(JSON.stringify({ error: 'not found' })) }
        const c = row.split('|')
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
        return res.end(JSON.stringify({ id: c[0], status: c[1], current_agent: c[2], current_step: +c[3], total_steps: +c[4], created_at: c[5], updated_at: c[6], finished_at: c[7], metadata: JSON.parse(c[8] || '{}') }))
      }
      if (req.method === 'POST' && !runId) {
        const body = await readJson(req)
        const id = body.run_id || 'run-' + Date.now()
        const now = new Date().toISOString()
        sqlExecMany(DB_WORKFLOW, `INSERT OR REPLACE INTO workflow_runs (id, status, current_agent, current_step, total_steps, created_at, updated_at, metadata) VALUES ('${id.replace(/'/g, "''")}', 'running', NULL, 0, ${body.total_steps || 5}, '${now}', '${now}', '${JSON.stringify(body.metadata || {}).replace(/'/g, "''")}');`)
        res.writeHead(201, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
        return res.end(JSON.stringify({ id, status: 'running' }))
      }
      if (req.method === 'POST' && runId) {
        const body = await readJson(req)
        const runRaw = await sqlExec(DB_WORKFLOW, "SELECT id, status, current_step, total_steps FROM workflow_runs WHERE id = ?", [runId])
        if (!runRaw) { res.writeHead(404); return res.end(JSON.stringify({ error: 'not found' })) }
        const rc = runRaw.split('|')
        const cur = +rc[2], total = +rc[3]
        const nxt = Math.min(cur + 1, total)
        const now = new Date().toISOString()
        const agent = (body.agent_id || '').replace(/'/g, "''")
        const payload = JSON.stringify(body.payload || {}).replace(/'/g, "''")
        await sqlExecMany(DB_WORKFLOW, `UPDATE workflow_runs SET current_step=${nxt}, current_agent='${agent || ''}', updated_at='${now}' WHERE id='${runId.replace(/'/g, "''")}'; INSERT INTO workflow_events (run_id, ts, agent_id, event_type, payload) VALUES ('${runId.replace(/'/g, "''")}', '${now}', '${agent || 'system'}', 'agent_completed', '${payload}');`)
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
        return res.end(JSON.stringify({ run_id: runId, current_step: nxt, total_steps: total }))
      }
    }

    if (parts[0] === 'api' && parts[1] === 'tokens') {
      if (parts[2] === 'totals' && req.method === 'GET') {
        const runId = url.searchParams.get('project')
        const sql = runId ? "SELECT COALESCE(SUM(est_cost_usd),0) FROM token_usages WHERE run_id = ?" : "SELECT COALESCE(SUM(est_cost_usd),0) FROM token_usages"
        const total = parseFloat(runId ? await sqlExec(DB_TRACKING, sql, [runId]) : await sqlExec(DB_TRACKING, sql))
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
        return res.end(JSON.stringify({ run_id: runId || null, total_cost_usd: total }))
      }
      if (parts[2] === 'budgets' && req.method === 'GET') {
        const out = await sqlExec(DB_TRACKING, "SELECT agent_id, budget_per_run, max_consecutive_runs, updated_at FROM agent_budgets ORDER BY agent_id")
        const rows = out ? out.split('\n') : []
        const data = rows.map(r => { const c = r.split('|'); return { agent_id: c[0], budget_per_run: +c[1], max_consecutive_runs: +c[2], updated_at: c[3] } })
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
        return res.end(JSON.stringify(data))
      }
      if (parts[2] === 'usage' && req.method === 'POST') {
        const body = await readJson(req)
        const now = new Date().toISOString()
        const id = body.run_id || 'run-local'
        sqlExecMany(DB_TRACKING, `INSERT INTO token_usages (ts, run_id, agent_id, prompt_tokens, completion_tokens, total_tokens, est_cost_usd, model) VALUES ('${now}', '${id.replace(/'/g, "''")}', '${(body.agent_id || '').replace(/'/g, "''")}', ${Math.max(0, +body.prompt_tokens || 0)}, ${Math.max(0, +body.completion_tokens || 0)}, ${Math.max(0, +body.prompt_tokens || 0) + Math.max(0, +body.completion_tokens || 0)}, ${Math.max(0, +body.est_cost_usd || 0)}, '${(body.model || '').replace(/'/g, "''")}');`)
        res.writeHead(201, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
        return res.end(JSON.stringify({ recorded: true }))
      }
    }

    if (parts[0] === 'api' && parts[1] === 'allocation') {
      if (parts[2] === 'rules') {
        if (req.method === 'GET') {
          const p = path.join(ROOT, 'data', 'allocation_rules.json')
          if (!fs.existsSync(p)) {
            res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
            return res.end(JSON.stringify({ owner_payout_pct: 0.6, ai_reinvestment_pct: 0.25, emergency_reserve_pct: 0.15 }))
          }
          const raw = fs.readFileSync(p, 'utf8')
          res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
          return res.end(raw)
        }
        if (req.method === 'PUT') {
          const body = await readJson(req)
          const p = path.join(ROOT, 'data', 'allocation_rules.json')
          fs.mkdirSync(path.dirname(p), { recursive: true })
          fs.writeFileSync(p, JSON.stringify(body, null, 2), 'utf8')
          res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
          return res.end(JSON.stringify({ saved: true, path: p }))
        }
      }
      if (parts[2] === 'history' && req.method === 'GET') {
        const out = await sqlExec(DB_ALLOCATION, "SELECT id, year, month, owner_payout_usd, ai_reinvestment_usd, emergency_reserve_usd, rules_snapshot, created_at FROM monthly_allocations ORDER BY year DESC, month DESC")
        const rows = out ? out.split('\n') : []
        const data = rows.map(r => { const c = r.split('|'); return { id: c[0], year: +c[1], month: +c[2], owner_payout_usd: +c[3], ai_reinvestment_usd: +c[4], emergency_reserve_usd: +c[5], rules: JSON.parse(c[6]), created_at: c[7] } })
        res.writeHead(200, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
        return res.end(JSON.stringify(data))
      }
    }

    res.writeHead(404, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' })
    res.end(JSON.stringify({ error: 'not found', path: url.pathname }))
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'application/json' })
    res.end(JSON.stringify({ error: String(e) }))
  }
}

initDBs()
const srv = http.createServer(handler)
srv.listen(PORT, HOST, () => { console.log('AI Freelance Swarm API on http://' + HOST + ':' + PORT) })
