/**
 * sendTele_v2.gs — Google Apps Script trigger for Google Form -> Telegram webhook
 *
 * Setup:
 *   1. In your Google Form, open Extensions -> Apps Script
 *   2. Paste this file (rename Code.gs if needed)
 *   3. Set WEBHOOK_URL and WEBHOOK_SECRET in Project Settings -> Script Properties:
 *        WEBHOOK_URL   = https://your.domain.example/webhook/form
 *        WEBHOOK_SECRET = <32+ char random string; same as notifier env>
 *   4. Run `installTrigger()` once to register the onFormSubmit trigger
 *   5. Authorize the script (it needs UrlFetchApp + FormApp permissions)
 *
 * Manual test: run `sendTestSubmission()` from the editor.
 */

/** @private */
var PROP_KEY_URL = "WEBHOOK_URL";
/** @private */
var PROP_KEY_SECRET = "WEBHOOK_SECRET";

/**
 * Trigger entry point. Registered via installTrigger().
 * @param {GoogleAppsScript.Events.FormsOnFormSubmitEvent} e
 */
function onFormSubmit(e) {
  try {
    var payload = buildPayload_(e);
    var body = JSON.stringify(payload);
    var sig = computeHmacHex_(body);
    postToWebhook_(body, sig);
  } catch (err) {
    Logger.log("onFormSubmit failed: " + err && err.stack ? err.stack : err);
  }
}

/**
 * Build the JSON payload from a form-submit event.
 * @param {GoogleAppsScript.Events.FormsOnFormSubmitEvent} e
 * @return {{form_id: string, submitted_at: string, responses: Array<{index: number, title: string, answer: string}>}}
 * @private
 */
function buildPayload_(e) {
  var form = FormApp.getActiveForm();
  var items = form.getItems();
  var responses = [];
  for (var i = 0; i < items.length; i++) {
    var title = items[i].getTitle();
    var named = e.namedValues && e.namedValues[title];
    var answer = (named && named.length > 0) ? String(named[0]) : "";
    responses.push({ index: i, title: title, answer: answer });
  }
  return {
    form_id: form.getId(),
    submitted_at: new Date().toISOString(),
    responses: responses,
  };
}

/**
 * Compute HMAC-SHA256(secret, body) and return lowercase hex.
 * @param {string} body
 * @return {string}
 * @private
 */
function computeHmacHex_(body) {
  var props = PropertiesService.getScriptProperties();
  var secret = props.getProperty(PROP_KEY_SECRET);
  if (!secret) throw new Error("WEBHOOK_SECRET not set in Script Properties");
  var bytes = Utilities.newBlob(body, "application/json").getBytes();
  var sig = Utilities.computeHmacSha256Signature(secret, bytes);
  return sig.map(function (b) {
    var h = (b & 0xff).toString(16);
    return h.length === 1 ? "0" + h : h;
  }).join("");
}

/**
 * POST the signed body to the webhook URL.
 * @param {string} body
 * @param {string} sigHex
 * @private
 */
function postToWebhook_(body, sigHex) {
  var url = PropertiesService.getScriptProperties().getProperty(PROP_KEY_URL);
  if (!url) throw new Error("WEBHOOK_URL not set in Script Properties");
  var resp = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: body,
    headers: { "X-Signature": sigHex },
    muteHttpExceptions: true,
  });
  var code = resp.getResponseCode();
  if (code < 200 || code >= 300) {
    Logger.log("Webhook returned " + code + ": " + resp.getContentText());
  } else {
    Logger.log("Webhook OK: " + code);
  }
}

/**
 * Register the onFormSubmit trigger. Run this once after pasting the script.
 * Re-running is safe — it deletes existing triggers first.
 */
function installTrigger() {
  var form = FormApp.getActiveForm();
  var existing = ScriptApp.getUserTriggers(form);
  for (var i = 0; i < existing.length; i++) {
    if (existing[i].getEventType() === ScriptApp.EventType.ON_FORM_SUBMIT) {
      ScriptApp.deleteTrigger(existing[i]);
    }
  }
  ScriptApp.newTrigger("onFormSubmit")
    .forForm(form)
    .onFormSubmit()
    .create();
  Logger.log("Trigger installed.");
}

/**
 * Manual test: builds a fake payload, signs it, posts to the webhook.
 * Use this to verify your WEBHOOK_URL + WEBHOOK_SECRET are correct
 * before relying on real form submissions.
 */
function sendTestSubmission() {
  var fakeEvent = {
    namedValues: {
      "Nama": ["Budi Santoso"],
      "NIP": ["123456789012345678"],
      "Instansi": ["BPS Provinsi"],
    },
  };
  var form = FormApp.getActiveForm();
  var items = form.getItems();
  var responses = [];
  for (var i = 0; i < items.length; i++) {
    var t = items[i].getTitle();
    responses.push({
      index: i,
      title: t,
      answer: (fakeEvent.namedValues[t] && fakeEvent.namedValues[t][0]) || "",
    });
  }
  var payload = {
    form_id: form.getId(),
    submitted_at: new Date().toISOString(),
    responses: responses,
  };
  var body = JSON.stringify(payload);
  var sig = computeHmacHex_(body);
  postToWebhook_(body, sig);
}
