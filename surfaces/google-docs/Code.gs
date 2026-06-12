/**
 * Help Me Write Better — Google Docs editor add-on.
 *
 * Adds a sidebar: select text, pick a service, and Improve replaces the
 * selection in place. Calls the project's public JSON API (POST /) via
 * UrlFetchApp. The engine URL is stored per-user in script properties.
 */

function onOpen() {
  DocumentApp.getUi()
    .createMenu('Help Me Write Better')
    .addItem('Open sidebar', 'showSidebar')
    .addToUi();
}

function onInstall(e) {
  onOpen();
}

function showSidebar() {
  var html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('Help Me Write Better');
  DocumentApp.getUi().showSidebar(html);
}

/** Plain text of the current selection (empty string if nothing is selected). */
function getSelectionText() {
  var sel = DocumentApp.getActiveDocument().getSelection();
  if (!sel) return '';
  var parts = [];
  var els = sel.getRangeElements();
  for (var i = 0; i < els.length; i++) {
    var re = els[i];
    var el = re.getElement();
    if (!el.editAsText) continue;
    var full = el.asText().getText();
    if (re.isPartial()) {
      parts.push(full.substring(re.getStartOffset(), re.getEndOffsetInclusive() + 1));
    } else {
      parts.push(full);
    }
  }
  return parts.join('');
}

/** Replace the current selection with `text`, in document order. */
function replaceSelectionWith(text) {
  var sel = DocumentApp.getActiveDocument().getSelection();
  if (!sel) throw new Error('Select some text first.');
  var els = sel.getRangeElements();
  var inserted = false;
  for (var i = 0; i < els.length; i++) {
    var re = els[i];
    var el = re.getElement();
    if (!el.editAsText) continue;
    var t = el.asText();
    var start = re.isPartial() ? re.getStartOffset() : 0;
    var end = re.isPartial() ? re.getEndOffsetInclusive() : t.getText().length - 1;
    if (end >= start) t.deleteText(start, end);
    if (!inserted) {
      t.insertText(start, text);
      inserted = true;
    }
  }
  if (!inserted) throw new Error('Could not edit the selected text.');
}

/** Improve the selection with the given service; returns the new text. */
function improveSelection(service) {
  var text = getSelectionText().trim();
  if (!text) throw new Error('Select some text in the document first.');
  var out = callApi(text, service);
  replaceSelectionWith(out);
  return out;
}

function callApi(text, service) {
  var base = getApiBase();
  var res = UrlFetchApp.fetch(base + '/', {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify({ text: text, services: [service], format: 'plain' }),
    muteHttpExceptions: true
  });
  var data = JSON.parse(res.getContentText() || '{}');
  if (res.getResponseCode() >= 300) {
    throw new Error(data.error || ('HTTP ' + res.getResponseCode()));
  }
  return data.text;
}

function getApiBase() {
  var v = PropertiesService.getUserProperties().getProperty('apiBase');
  return (v || 'http://localhost:8000').replace(/\/+$/, '');
}

function setApiBase(value) {
  var clean = (value || '').trim().replace(/\/+$/, '');
  PropertiesService.getUserProperties().setProperty('apiBase', clean);
  return getApiBase();
}
