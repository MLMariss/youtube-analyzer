/**
 * The action log: where the dashboard's "Log action" saves what you did.
 * It also starts the hourly edit watcher: GitHub runs this repository's own
 * schedules hours late or not at all, while Apps Script's run on time.
 *
 * Setup (once, about five minutes; README "Action log"):
 *   1. Make a new Google Sheet. Extensions → Apps Script. Replace the code
 *      with this file and save.
 *   2. Project Settings (gear) → Script properties → Add: KEY = a long random
 *      password. The dashboard and the hourly watcher both need it.
 *   3. Deploy → New deployment → type Web app. Execute as: Me. Who has access:
 *      Anyone. Deploy, allow access, copy the Web app URL.
 *   4. On GitHub, make a fine-grained personal access token for this
 *      repository only, with the permission Actions: Read and write. Add it as
 *      a second script property, GITHUB_TOKEN. In the editor, pick
 *      installWatchTrigger in the function list, Run, and allow access.
 *
 * Every row is one action. Edit or delete rows here: the watcher reads the
 * whole sheet every hour, and a deleted row deletes the action.
 */

const SHEET = 'Log';
const HEADERS = ['id', 'logged_at', 'video', 'what', 'date', 'situation', 'notes'];

function doPost(e) {
  let req;
  try {
    req = JSON.parse(e.postData.contents);
  } catch (err) {
    return reply({ ok: false, error: 'not JSON' });
  }
  const key = PropertiesService.getScriptProperties().getProperty('KEY');
  if (!key || req.key !== key) return reply({ ok: false, error: 'wrong key' });
  const sheet = logSheet();

  if (req.action === 'list') {
    const rows = sheet.getDataRange().getDisplayValues().slice(1).filter(r => r[0]);
    return reply({ ok: true, rows: rows.map(r => Object.fromEntries(HEADERS.map((h, i) => [h, r[i]]))) });
  }
  if (req.action === 'add') {
    if (!req.video || !req.what) return reply({ ok: false, error: 'video and what are required' });
    const id = Utilities.getUuid().slice(0, 8);
    const lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      sheet.appendRow([id, new Date().toISOString(), String(req.video), String(req.what),
                       String(req.date || ''), String(req.situation || ''), String(req.notes || '').slice(0, 500)]);
    } finally {
      lock.releaseLock();
    }
    return reply({ ok: true, id: id });
  }
  return reply({ ok: false, error: 'unknown action' });
}

// The log tab, made on first use. Every cell is plain text, so a date stays
// 2026-11-19 instead of turning into a date in your Sheet's own format.
function logSheet() {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = book.getSheetByName(SHEET);
  if (!sheet) {
    sheet = book.insertSheet(SHEET);
    sheet.getRange('A:G').setNumberFormat('@');
    sheet.appendRow(HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function reply(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}

// ------------------------------------------------------------ the hourly watcher

const REPO = 'MLMariss/youtube-analyzer';

// Starts the "Watch for edits" workflow on main. If GitHub refuses (a missing,
// wrong or expired GITHUB_TOKEN), the run fails and Apps Script emails you.
function startWatcher() {
  const token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('add the script property GITHUB_TOKEN (setup step 4)');
  const res = UrlFetchApp.fetch(`https://api.github.com/repos/${REPO}/actions/workflows/watch.yml/dispatches`, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28' },
    payload: JSON.stringify({ ref: 'main' }),
    muteHttpExceptions: true,
  });
  const code = res.getResponseCode();
  if (code < 200 || code >= 300) {
    throw new Error(`GitHub did not start the watcher (${code}): ${res.getContentText().slice(0, 200)}`);
  }
}

// Run once from the editor (setup step 4). Running it again replaces the
// hourly trigger instead of adding a second one. It also starts the watcher
// once straight away, so a wrong token shows up now, not in an hour.
function installWatchTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'startWatcher')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('startWatcher').timeBased().everyHours(1).create();
  startWatcher();
}
