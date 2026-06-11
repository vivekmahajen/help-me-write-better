/**
 * Google Docs Workspace Add-on — a card-based sidebar that checks the document
 * via the platform gateway and applies accepted fixes. Thin client of /v1/check
 * and /v1/improve. Pure helpers (wb*) live in helpers.js, shared with the tests.
 *
 * Config (API base URL + key) is stored per-user in PropertiesService.
 */

function getConfig_() {
  var props = PropertiesService.getUserProperties();
  return {
    baseUrl: props.getProperty('wb_base_url') || 'http://localhost:8000',
    apiKey: props.getProperty('wb_api_key') || '',
  };
}

function callGateway_(path, payload) {
  var cfg = getConfig_();
  var res = UrlFetchApp.fetch(cfg.baseUrl.replace(/\/+$/, '') + path, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + cfg.apiKey },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });
  var data = JSON.parse(res.getContentText() || '{}');
  if (res.getResponseCode() >= 300) {
    throw new Error(data.error || ('HTTP ' + res.getResponseCode()));
  }
  return data;
}

/** Entry point (declared as homepageTrigger in appsscript.json). */
function onHomepage(e) {
  var cfg = getConfig_();
  var builder = CardService.newCardBuilder();

  var settings = CardService.newCardSection().setHeader('Settings')
    .addWidget(CardService.newTextInput().setFieldName('base_url')
      .setTitle('API base URL').setValue(cfg.baseUrl))
    .addWidget(CardService.newTextInput().setFieldName('api_key')
      .setTitle('API key').setValue(cfg.apiKey))
    .addWidget(CardService.newTextButton().setText('Save')
      .setOnClickAction(CardService.newAction().setFunctionName('saveSettings_')));

  var actions = CardService.newCardSection()
    .addWidget(CardService.newTextButton().setText('Check document')
      .setOnClickAction(CardService.newAction().setFunctionName('checkDocument_')));

  return builder.addSection(settings).addSection(actions).build();
}

function saveSettings_(e) {
  var props = PropertiesService.getUserProperties();
  props.setProperty('wb_base_url', e.formInput.base_url || '');
  props.setProperty('wb_api_key', e.formInput.api_key || '');
  return notify_('Settings saved.');
}

function checkDocument_(e) {
  var text = DocumentApp.getActiveDocument().getBody().getText();
  var data;
  try {
    data = callGateway_('/v1/check', wbBuildCheckBody(text));
  } catch (err) {
    return notify_('Error: ' + err.message);
  }
  var suggestions = wbSortSuggestions(data.suggestions || []);

  var section = CardService.newCardSection()
    .setHeader(suggestions.length + ' suggestion(s)');
  if (!suggestions.length) {
    section.addWidget(CardService.newTextParagraph().setText('No issues found.'));
  }
  for (var i = 0; i < Math.min(suggestions.length, 20); i++) {
    var s = suggestions[i];
    var original = wbSliceForRange(text, s.range);
    section.addWidget(CardService.newDecoratedText()
      .setText(wbFormatSuggestion(s)).setBottomLabel(original).setWrapText(true));
    if (s.replacements && s.replacements.length) {
      var action = CardService.newAction().setFunctionName('applyFix_')
        .setParameters({ original: original, replacement: s.replacements[0] || '' });
      section.addWidget(CardService.newTextButton()
        .setText('Fix → ' + (s.replacements[0] || '(delete)')).setOnClickAction(action));
    }
  }

  var card = CardService.newCardBuilder().addSection(section).build();
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(card)).build();
}

function applyFix_(e) {
  var body = DocumentApp.getActiveDocument().getBody();
  body.replaceText(wbEscapeRegex(e.parameters.original), e.parameters.replacement);
  return notify_('Applied.');
}

function notify_(text) {
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText(text)).build();
}
