const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('web/app.js', 'utf8');
const context = {URLSearchParams, window: {location: {search: '?preview=1'}}};
vm.createContext(context);
vm.runInContext(source.slice(0, source.indexOf('const state =')), context);
assert.equal(vm.runInContext('previewData.lineItems.length', context), 5);
assert.ok(vm.runInContext('previewData.lineItems.every(x => x.customer_name.includes("虚构"))', context));
const csv = source.slice(source.indexOf('function csvEscape('), source.indexOf('function exportToCSV('));
vm.runInContext(csv, context);
for (const value of ['=1+1', '+SUM(A1)', '@SUM(A1)', '-1+1', '\t=1']) {
  assert.ok(context.csvEscape(value).replace(/^"/, '').startsWith("'"), value);
}
assert.equal(context.csvEscape('ordinary'), 'ordinary');
const declarations = source.slice(source.indexOf('const LINE_COLUMNS_ALL'), source.indexOf('function getColumnClassName'));
vm.runInContext(declarations, context);
assert.equal(vm.runInContext('LINE_COLUMNS_ALL[4].key', context), 'bandwidth');
assert.equal(vm.runInContext('LINE_COLUMNS_ALL[5].key', context), 'access_method');
assert.equal(vm.runInContext('getLineColumns("互联网专线")[4].key', context), 'access_method');
console.log('Frontend fixtures, CSV safety and column order passed');
assert.equal(context.csvEscape('alpha\rbeta'), '"alpha\rbeta"');
assert.equal(context.csvEscape('a,b'), '"a,b"');
assert.equal(context.csvEscape('a"b'), '"a""b"');
assert.equal(context.csvEscape(null), '');
assert.equal(context.csvEscape('示例字段'), '示例字段');
assert.equal(context.csvEscape('00123'), '00123');

// Preview must neither send real requests nor overwrite a live user's token.
context.fetch = () => { throw new Error('Unexpected real network request'); };
context.window.localStorage = {
  setItem() { throw new Error('Unexpected token write'); },
  removeItem() { throw new Error('Unexpected token deletion'); },
};
vm.runInContext('const state = {auth: {token: ""}};', context);
vm.runInContext(source.slice(source.indexOf('function saveToken('), source.indexOf('function setSession(')), context);
context.saveToken('preview-token');
vm.runInContext(source.slice(source.indexOf('async function requestJSON('), source.indexOf('function setTableEmpty(')), context);
(async () => {
  const result = await context.requestJSON('/api/auth/me');
  assert.equal(result.user.username, 'admin');
  await assert.rejects(context.requestJSON('/api/unknown'), /预览模式不访问真实接口/);
  await context.requestJSON('/api/admin/import/run', {method: 'POST'});
  console.log('CSV round-trip cases and preview isolation passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
