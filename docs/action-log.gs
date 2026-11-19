/**
 * The action log: where the dashboard's "Log action" saves what you did.
 *
 * Setup (once, about five minutes; README "Action log"):
 *   1. Make a new Google Sheet. Extensions → Apps Script. Replace the code
 *      with this file and save.
 *   2. Project Settings (gear) → Script properties → Add: KEY = a long random
 *      password. The dashboard and the hourly watcher both need it.
 *   3. Deploy → New deployment → type Web app. Execute as: Me. Who has access:
 *      Anyone. Deploy, allow access, copy the Web app URL.
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
