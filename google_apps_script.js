/**
 * Google Apps Script for Brevo Lead Outreach Stats Dashboard
 *
 * INSTRUCTIONS:
 * 1. Create a new Google Sheet
 * 2. Go to Extensions > Apps Script
 * 3. Delete any code there and paste this entire file
 * 4. Click Deploy > New deployment
 * 5. Choose type: "Web app"
 * 6. Description: "Brevo Stats Updater"
 * 7. Execute as: "Me"
 * 8. Who has access: "Anyone"
 * 9. Click Deploy, authorize when prompted
 * 10. Copy the web app URL and share it with me
 */

var AUTH_TOKEN = "cmp-lead-stats-2026";
var SUMMARY_SHEET = "Summary";
var DETAIL_SHEET = "Detail";

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({"status": "ok", "message": "Brevo Stats endpoint is running"}))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    // Verify auth token
    if (data.auth_token !== AUTH_TOKEN) {
      return ContentService.createTextOutput(JSON.stringify({"status": "error", "message": "Unauthorized"}))
        .setMimeType(ContentService.MimeType.JSON);
    }

    var ss = SpreadsheetApp.getActiveSpreadsheet();

    // Ensure sheets exist
    var summarySheet = ss.getSheetByName(SUMMARY_SHEET);
    if (!summarySheet) {
      summarySheet = ss.insertSheet(SUMMARY_SHEET);
    }

    var detailSheet = ss.getSheetByName(DETAIL_SHEET);
    if (!detailSheet) {
      detailSheet = ss.insertSheet(DETAIL_SHEET);
    }

    // Update Summary sheet
    updateSummary(summarySheet, data.summaries || []);

    // Update Detail sheet
    updateDetail(detailSheet, data.events || []);

    return ContentService.createTextOutput(JSON.stringify({
      "status": "ok",
      "summaries_updated": (data.summaries || []).length,
      "events_updated": (data.events || []).length,
      "timestamp": new Date().toISOString()
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      "status": "error",
      "message": err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function updateSummary(sheet, summaries) {
  var headers = [
    "Last Updated", "Account", "Date",
    "Sent (Requests)", "Delivered", "Opens", "Unique Opens",
    "Clicks", "Unique Clicks", "Hard Bounces", "Soft Bounces",
    "Unsubscribed", "Spam Reports", "Blocked", "Deferred", "Errors",
    "Delivery Rate %", "Open Rate %", "Click Rate %", "Bounce Rate %"
  ];

  // Check if header row exists
  var existingHeaders = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  var hasHeaders = existingHeaders[0] === "Last Updated";

  if (!hasHeaders) {
    sheet.clear();
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
    sheet.getRange(1, 1, 1, headers.length).setBackground("#4285f4");
    sheet.getRange(1, 1, 1, headers.length).setFontColor("#ffffff");
    sheet.setFrozenRows(1);
  }

  // Find existing rows for today and update them, or append new
  var now = new Date();
  var todayStr = Utilities.formatDate(now, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm");

  for (var i = 0; i < summaries.length; i++) {
    var s = summaries[i];
    var delivered = s.delivered || 0;
    var requests = s.requests || 0;
    var opens = s.opens || 0;
    var clicks = s.clicks || 0;
    var hardBounces = s.hardBounces || 0;
    var softBounces = s.softBounces || 0;
    var totalBounces = hardBounces + softBounces;

    var deliveryRate = requests > 0 ? (delivered / requests * 100).toFixed(1) : "0";
    var openRate = delivered > 0 ? (opens / delivered * 100).toFixed(1) : "0";
    var clickRate = delivered > 0 ? (clicks / delivered * 100).toFixed(1) : "0";
    var bounceRate = requests > 0 ? (totalBounces / requests * 100).toFixed(1) : "0";

    var row = [
      todayStr,
      s.account,
      s.date,
      requests,
      delivered,
      opens,
      s.uniqueOpens || 0,
      clicks,
      s.uniqueClicks || 0,
      hardBounces,
      softBounces,
      s.unsubscribed || 0,
      s.spamReports || 0,
      s.blocked || 0,
      s.deferred || 0,
      s.error || 0,
      deliveryRate + "%",
      openRate + "%",
      clickRate + "%",
      bounceRate + "%"
    ];

    // Find if this account already has a row for today
    var lastRow = sheet.getLastRow();
    var found = false;
    if (lastRow > 1) {
      var accountCol = sheet.getRange(2, 2, lastRow - 1, 1).getValues();
      var dateCol = sheet.getRange(2, 3, lastRow - 1, 1).getValues();
      for (var r = 0; r < accountCol.length; r++) {
        if (accountCol[r][0] === s.account && dateCol[r][0] === s.date) {
          sheet.getRange(r + 2, 1, 1, headers.length).setValues([row]);
          found = true;
          break;
        }
      }
    }

    if (!found) {
      sheet.appendRow(row);
    }
  }

  // Format columns
  sheet.autoResizeColumns(1, headers.length);
}

function updateDetail(sheet, events) {
  var headers = [
    "Timestamp", "Email", "Event", "Category", "Account",
    "Subject", "Link", "From", "Template ID", "Tag", "Message ID"
  ];

  // Check if header row exists
  var existingHeaders = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  var hasHeaders = existingHeaders[0] === "Timestamp";

  if (!hasHeaders) {
    sheet.clear();
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
    sheet.getRange(1, 1, 1, headers.length).setBackground("#FF1A66");
    sheet.getRange(1, 1, 1, headers.length).setFontColor("#ffffff");
    sheet.setFrozenRows(1);
  }

  // Collect existing message IDs to avoid duplicates
  var lastRow = sheet.getLastRow();
  var existingMsgIds = {};
  if (lastRow > 1) {
    var msgIdCol = sheet.getRange(2, 11, lastRow - 1, 1).getValues();
    var eventCol = sheet.getRange(2, 3, lastRow - 1, 1).getValues();
    var emailCol = sheet.getRange(2, 2, lastRow - 1, 1).getValues();
    for (var r = 0; r < msgIdCol.length; r++) {
      var key = emailCol[r][0] + "|" + msgIdCol[r][0] + "|" + eventCol[r][0];
      existingMsgIds[key] = true;
    }
  }

  // Add new events (avoid duplicates)
  var newRows = [];
  for (var i = 0; i < events.length; i++) {
    var ev = events[i];
    var key = ev.email + "|" + ev.messageId + "|" + ev.event;
    if (existingMsgIds[key]) {
      continue;
    }
    existingMsgIds[key] = true;

    newRows.push([
      ev.date || "",
      ev.email || "",
      ev.event || "",
      ev.category || "",
      ev.account || "",
      ev.subject || "",
      ev.link || "",
      ev.from || "",
      ev.templateId || "",
      ev.tag || "",
      ev.messageId || ""
    ]);
  }

  if (newRows.length > 0) {
    // Sort by timestamp descending
    newRows.sort(function(a, b) {
      return b[0].localeCompare(a[0]);
    });

    // Insert at row 2 (after headers) to show newest first
    sheet.insertRows(2, newRows.length);
    sheet.getRange(2, 1, newRows.length, headers.length).setValues(newRows);

    // Color-code event types
    var eventRange = sheet.getRange(2, 3, newRows.length, 1);
    var eventValues = eventRange.getValues();
    var backgrounds = [];
    for (var j = 0; j < eventValues.length; j++) {
      var evt = eventValues[j][0];
      if (evt === "delivered" || evt === "requests") {
        backgrounds.push(["#d4edda"]); // green
      } else if (evt === "opens" || evt === "loadedByProxy") {
        backgrounds.push(["#cce5ff"]); // blue
      } else if (evt === "clicks") {
        backgrounds.push(["#fff3cd"]); // yellow
      } else if (evt === "hardBounces" || evt === "softBounces" || evt === "error" || evt === "blocked") {
        backgrounds.push(["#f8d7da"]); // red
      } else if (evt === "unsubscribed" || evt === "spamReports") {
        backgrounds.push(["#e2d6f3"]); // purple
      } else {
        backgrounds.push([null]);
      }
    }
    // Apply backgrounds (skip nulls)
    for (var k = 0; k < backgrounds.length; k++) {
      if (backgrounds[k][0]) {
        sheet.getRange(k + 2, 3, 1, 1).setBackground(backgrounds[k][0]);
      }
    }
  }

  sheet.autoResizeColumns(1, headers.length);
}
