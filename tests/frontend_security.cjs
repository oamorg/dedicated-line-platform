const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/app.js', 'utf8');
const html = fs.readFileSync('web/index.html', 'utf8');
const css = fs.readFileSync('web/styles.css', 'utf8');
for (const id of ['appShell', 'detailDrawer']) {
  assert.match(html, new RegExp(`<[^>]+id="${id}"[^>]*\\bhidden\\b[^>]*\\binert\\b`));
}
assert.match(css, /\[hidden\]\s*\{\s*display:\s*none\s*!important;/);
class Element {
  constructor() {
    this.innerHTML = '';
    this.style = {};
    this.classList = {add() {}, remove() {}, toggle() {}};
  }
  set textContent(value) { this.innerHTML = value; }
  get textContent() { return this.innerHTML; }
  reset() { this.wasReset = true; }
  addEventListener() {}
}
const nodes = new Map();
const listeners = new Map();
const storage = new Map();
const loggedErrors = [];
const context = {console: {...console, error: error => loggedErrors.push(error)}, URLSearchParams, AbortController, DOMException,
  document: {getElementById(id) {
    if (!nodes.has(id)) nodes.set(id, new Element());
    return nodes.get(id);
  }, querySelectorAll: () => []},
  window: {location: {search: ''}, addEventListener: (key, callback) => listeners.set(key, callback),
    localStorage: {getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k)}},
};
vm.createContext(context);
vm.runInContext(source.slice(0, source.lastIndexOf('init();')), context);
const evaluate = text => vm.runInContext(text, context);
const user = {id: 1, username: 'synthetic', permissions: ['data.query']};
const ok = data => ({ok: true, status: 200, json: async () => data});
const deferred = () => {let resolve; const promise = new Promise(r => {resolve = r;}); return {promise, resolve};};
const assertProtected = hidden => {
  for (const id of ['appShell', 'detailDrawer']) {
    assert.equal(nodes.get(id).hidden, hidden, `${id} visibility`);
    assert.equal(nodes.get(id).inert, hidden, `${id} interaction`);
  }
};

(async () => {
  context.updateAuthUI();
  assertProtected(true);
  context.hideAuthGate();
  assertProtected(true); // A UI call alone must not reveal the shell.
  storage.set('dedicated_line_token', 'unverified-token');
  const verification = deferred();
  context.fetch = () => verification.promise;
  const restoring = context.tryRestoreSession();
  assertProtected(true);
  verification.resolve({ok: false, status: 401, headers: {get: () => null}, json: async () => ({detail: 'expired'})});
  await restoring;
  assert.equal(loggedErrors.at(-1).status, 401);
  assertProtected(true);

  context.setSession('synthetic-token', user);
  assertProtected(true);
  context.hideAuthGate();
  assertProtected(false);
  assert.equal(nodes.get('authGate').hidden, true);
  evaluate('state.onu.items = [{onu_password: "synthetic-secret"}]; state.admin.users = [{username: "synthetic-admin"}];');
  nodes.get('drawerRaw').textContent = 'synthetic-secret';
  nodes.get('onuTableBody').innerHTML = '<td>synthetic-secret</td>';
  const query = deferred();
  context.fetch = async (url, options) => {
    if (url.includes('/api/auth/logout')) {
      assert.equal(options.headers.Authorization, 'Bearer synthetic-token');
      return ok({});
    }
    return query.promise; // Deliberately ignore abort to test the epoch guard too.
  };
  const pending = context.fetchLines();
  const rejected = assert.rejects(pending, {name: 'AbortError'});
  const logout = context.logout();
  assertProtected(true);
  assert.equal(nodes.get('authGate').hidden, false);
  assert.equal(evaluate('state.auth.token'), '');
  assert.equal(evaluate('state.onu.items.length + state.admin.users.length'), 0);
  assert.equal(nodes.get('drawerRaw').textContent, '');
  assert.equal(nodes.get('onuTableBody').innerHTML, '');
  query.resolve(ok({items: [{customer_name: 'private'}], total: 1}));
  await rejected;
  await logout;
  assert.equal(evaluate('state.line.items.length'), 0);

  context.setSession('old', user);
  const old = deferred();
  context.fetch = () => old.promise;
  const oldRequest = context.requestJSON('/api/auth/me');
  const oldRejected = assert.rejects(oldRequest, {name: 'AbortError'});
  context.setSession('new', user);
  old.resolve({ok: false, status: 401, json: async () => ({detail: 'expired'})});
  await oldRejected;
  assert.equal(evaluate('state.auth.token'), 'new');

  const body = deferred();
  context.fetch = async () => ({ok: true, status: 200, json: () => body.promise});
  const parsing = context.requestJSON('/api/onu/search');
  const parsingRejected = assert.rejects(parsing, {name: 'AbortError'});
  await Promise.resolve();
  context.clearSession();
  assertProtected(true);
  body.resolve({items: [{onu_password: 'private'}]});
  await parsingRejected;

  context.setSession('other-tab-old', user);
  context.bindAuthEvents();
  storage.set('dedicated_line_token', 'other-tab-new');
  listeners.get('storage')({key: 'dedicated_line_token'});
  assertProtected(true);
  assert.equal(evaluate('state.auth.token'), '');
  assert.equal(storage.get('dedicated_line_token'), 'other-tab-new');
  const admin = {...user, permissions: ['data.query', 'user.manage']};
  context.setSession('security-admin', admin);
  nodes.get('securityRuleForm').elements = {namedItem: () => ({value: ''})};
  context.fetch = async url => {
    if (url.includes('/rules')) return ok({rules: {window_seconds: 900, account_limit: 10, ip_limit: 60, version: 0}, client_ip: '192.0.2.1'});
    if (url.includes('/ip-blocks')) return ok({items: [{ip_address: '198.51.100.1', blocked_at: 1, expires_at: 2, reason: '<img src=x onerror=alert(1)>'}], total: 1});
    return ok({items: [{target_label: '<svg onload=alert(1)>', ip_address: '198.51.100.1', action_code: 'auth.login_limited', detail_json: {dimension: 'account', retry_after: 10}}], total: 1});
  };
  await context.refreshLoginSecurity();
  assert.ok(nodes.get('securityBlockBody').innerHTML.includes('&lt;img'));
  assert.ok(nodes.get('securityEventBody').innerHTML.includes('&lt;svg'));
  const staleSecurity = deferred();
  context.fetch = () => staleSecurity.promise;
  const refreshing = context.refreshLoginSecurity();
  const staleRejected = assert.rejects(refreshing, {name: 'AbortError'});
  context.clearSession();
  staleSecurity.resolve(ok({}));
  await staleRejected;
  assert.equal(nodes.get('securityBlockBody').textContent, '');
  assert.equal(nodes.get('securityEventBody').textContent, '');
  assert.equal(evaluate('state.security.rules'), null);
  context.setSession('security-admin-again', admin);
  const mutation = deferred();
  const saving = context.runSecurityAction(nodes.get('securityRuleSaveBtn'), () => mutation.promise);
  context.clearSession();
  mutation.resolve('Old operation completed');
  await saving;
  assert.equal(nodes.get('securityStatus').textContent, '');
  assert.equal(nodes.get('securityRuleSaveBtn').disabled, true);
  console.log('Login-security UI: escaped records, stale query/mutation rejection and logout cleanup passed');
  console.log('Frontend security: default-hidden shell, pending/failed verification, immediate hide/wipe, stale query/401/body rejection, account switch and cross-tab invalidation passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
