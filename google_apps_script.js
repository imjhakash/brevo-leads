/**
 * Google Apps Script for Brevo Lead Outreach Stats Dashboard
 * Version 2 - with Leads tab (one row per unique email, no duplicates)
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
 *
 * TABS:
 *   - Summary: daily totals per account (sent, delivered, opens, clicks, bounces, rates)
 *   - Leads: one row per unique email, color-coded status, no duplicates
 *   - Detail: raw per-email events (for debugging)
 */

var AUTH_TOKEN = "cmp-lead-stats-2026";
var SUMMARY_SHEET = "Summary";
var LEADS_SHEET = "Leads";
var DETAIL_SHEET = "Detail";

// Status priority (higher = shown first)
var STATUS_PRIORITY = {
  "clicks": 5,
  "opens": 4,
  "loadedByProxy": 4,
  "delivered": 3,
  "requests": 3,
  "softBounces": 2,
  "hardBounces": 1,
  "error": 1,
  "blocked": 1,
  "unsubscribed": 6,
  "spamReports": 6
};

// Status display names
var STATUS_DISPLAY = {
  "clicks": "Clicked",
  "opens": "Opened",
  "loadedByProxy": "Opened",
  "delivered": "Delivered",
  "requests": "Sent",
  "softBounces": "Soft Bounce",
  "hardBounces": "Hard Bounce",
  "error": "Error",
  "blocked": "Blocked",
  "unsubscribed": "Unsubscribed",
  "spamReports": "Spam Report"
};

// Status colors
var STATUS_COLORS = {
  "Clicked": "#cce5ff",       // blue
  "Opened": "#d4edda",         // green
  "Delivered": "#e8f5e9",      // light green
  "Sent": "#f5f5f5",           // light gray
  "Soft Bounce": "#fff3cd",    // yellow/orange
  "Hard Bounce": "#f8d7da",    // red
  "Error": "#f8d7da",          // red
  "Blocked": "#f8d7da",        // red
  "Unsubscribed": "#e2d6f3",   // purple
  "Spam Report": "#e2d6f3"     // purple
};

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
    if (!summarySheet) summarySheet = ss.insertSheet(SUMMARY_SHEET);

    var leadsSheet = ss.getSheetByName(LEADS_SHEET);
    if (!leadsSheet) leadsSheet = ss.insertSheet(LEADS_SHEET);

    var detailSheet = ss.getSheetByName(DETAIL_SHEET);
    if (!detailSheet) detailSheet = ss.insertSheet(DETAIL_SHEET);

    // Update each sheet
    updateSummary(summarySheet, data.summaries || []);
    updateLeads(leadsSheet, data.events || [], data.sent_emails || []);
    updateDetail(detailSheet, data.events || []);

    return ContentService.createTextOutput(JSON.stringify({
      "status": "ok",
      "summaries_updated": (data.summaries || []).length,
      "leads_updated": (data.sent_emails || []).length + (data.events || []).length,
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

// ============================================================
// SUMMARY TAB - daily totals per account
// ============================================================
function updateSummary(sheet, summaries) {
  var headers = [
    "Last Updated", "Account", "Date",
    "Sent (Requests)", "Delivered", "Opens", "Unique Opens",
    "Clicks", "Unique Clicks", "Hard Bounces", "Soft Bounces",
    "Unsubscribed", "Spam Reports", "Blocked", "Deferred", "Errors",
    "Delivery Rate %", "Open Rate %", "Click Rate %", "Bounce Rate %"
  ];

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
      todayStr, s.account, s.date,
      requests, delivered, opens, s.uniqueOpens || 0,
      clicks, s.uniqueClicks || 0, hardBounces, softBounces,
      s.unsubscribed || 0, s.spamReports || 0, s.blocked || 0,
      s.deferred || 0, s.error || 0,
      deliveryRate + "%", openRate + "%", clickRate + "%", bounceRate + "%"
    ];

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
    if (!found) sheet.appendRow(row);
  }
  sheet.autoResizeColumns(1, headers.length);
}

// ============================================================
// LEADS TAB - one row per unique email, color-coded, no duplicates
// ============================================================
function updateLeads(sheet, events, sentEmails) {
  var headers = [
    "Email", "Status", "Category", "Tag", "Account",
    "Subject", "First Sent", "Last Event", "Clicks Count", "Opens Count", "From"
  ];

  var existingHeaders = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  var hasHeaders = existingHeaders[0] === "Email";

  if (!hasHeaders) {
    sheet.clear();
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
    sheet.getRange(1, 1, 1, headers.length).setBackground("#FF1A66");
    sheet.getRange(1, 1, 1, headers.length).setFontColor("#ffffff");
    sheet.setFrozenRows(1);
  }

  // Build a map of existing leads in the sheet
  var lastRow = sheet.getLastRow();
  var leadsMap = {}; // email -> {rowIndex, status, statusPriority, clicks, opens, firstSent, lastEvent, category, tag, account, subject, from}

  if (lastRow > 1) {
    var allData = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
    for (var r = 0; r < allData.length; r++) {
      var email = allData[r][0];
      if (!email) continue;
      var statusStr = allData[r][1];
      var priority = 0;
      // Reverse-lookup priority from display name
      for (var key in STATUS_DISPLAY) {
        if (STATUS_DISPLAY[key] === statusStr) {
          priority = STATUS_PRIORITY[key] || 0;
          break;
        }
      }
      leadsMap[email] = {
        rowIndex: r + 2,
        status: statusStr,
        statusPriority: priority,
        category: allData[r][2],
        tag: allData[r][3],
        account: allData[r][4],
        subject: allData[r][5],
        firstSent: allData[r][6],
        lastEvent: allData[r][7],
        clicksCount: allData[r][8] || 0,
        opensCount: allData[r][9] || 0,
        from: allData[r][10] || ""
      };
    }
  }

  // Process sent emails first (these give us the base list of all leads)
  for (var i = 0; i < sentEmails.length; i++) {
    var se = sentEmails[i];
    var email = se.email;
    if (!email) continue;

    if (!leadsMap[email]) {
      leadsMap[email] = {
        rowIndex: -1, // new, will be appended
        status: "Sent",
        statusPriority: 3,
        category: se.category || "",
        tag: se.tag || "",
        account: se.account || "",
        subject: se.subject || "",
        firstSent: se.date || "",
        lastEvent: se.date || "",
        clicksCount: 0,
        opensCount: 0,
        from: se.from || ""
      };
    } else {
      // Update if sent date is earlier
      var existing = leadsMap[email];
      if (se.date && (!existing.firstSent || se.date < existing.firstSent)) {
        existing.firstSent = se.date;
      }
      if (!existing.category) existing.category = se.category || "";
      if (!existing.tag) existing.tag = se.tag || "";
      if (!existing.subject) existing.subject = se.subject || "";
      if (!existing.from) existing.from = se.from || "";
    }
  }

  // Process events (these update the status of each lead)
  for (var j = 0; j < events.length; j++) {
    var ev = events[j];
    var evEmail = ev.email;
    if (!evEmail) continue;

    var evType = ev.event || "";
    var evPriority = STATUS_PRIORITY[evType] || 0;
    var evDisplay = STATUS_DISPLAY[evType] || evType;

    if (!leadsMap[evEmail]) {
      // New lead from event (not in sent list)
      leadsMap[evEmail] = {
        rowIndex: -1,
        status: evDisplay,
        statusPriority: evPriority,
        category: ev.category || "",
        tag: ev.tag || "",
        account: ev.account || "",
        subject: ev.subject || "",
        firstSent: ev.date || "",
        lastEvent: ev.date || "",
        clicksCount: evType === "clicks" ? 1 : 0,
        opensCount: (evType === "opens" || evType === "loadedByProxy") ? 1 : 0,
        from: ev.from || ""
      };
    } else {
      var lead = leadsMap[evEmail];
      // Update status if this event has higher priority
      if (evPriority > lead.statusPriority) {
        lead.status = evDisplay;
        lead.statusPriority = evPriority;
      }
      // Update last event date
      if (ev.date && (!lead.lastEvent || ev.date > lead.lastEvent)) {
        lead.lastEvent = ev.date;
      }
      // Update first sent date
      if (ev.date && (!lead.firstSent || ev.date < lead.firstSent)) {
        lead.firstSent = ev.date;
      }
      // Count clicks and opens
      if (evType === "clicks") lead.clicksCount = (lead.clicksCount || 0) + 1;
      if (evType === "opens" || evType === "loadedByProxy") lead.opensCount = (lead.opensCount || 0) + 1;
      // Fill in missing fields
      if (!lead.category && ev.category) lead.category = ev.category;
      if (!lead.tag && ev.tag) lead.tag = ev.tag;
      if (!lead.subject && ev.subject) lead.subject = ev.subject;
      if (!lead.from && ev.from) lead.from = ev.from;
    }
  }

  // Now write back to sheet
  // First, update existing rows
  var updates = [];
  var updateRows = [];
  var newLeads = [];

  for (var emailKey in leadsMap) {
    var lead = leadsMap[emailKey];
    var row = [
      emailKey,
      lead.status,
      lead.category,
      lead.tag,
      lead.account,
      lead.subject,
      lead.firstSent,
      lead.lastEvent,
      lead.clicksCount,
      lead.opensCount,
      lead.from
    ];

    if (lead.rowIndex > 0) {
      updates.push({rowIndex: lead.rowIndex, data: row});
    } else {
      newLeads.push(row);
    }
  }

  // Update existing rows
  for (var u = 0; u < updates.length; u++) {
    sheet.getRange(updates[u].rowIndex, 1, 1, headers.length).setValues([updates[u].data]);
  }

  // Append new leads
  if (newLeads.length > 0) {
    // Sort by firstSent descending (newest first)
    newLeads.sort(function(a, b) {
      return (b[6] || "").localeCompare(a[6] || "");
    });
    sheet.getRange(lastRow + 1, 1, newLeads.length, headers.length).setValues(newLeads);
  }

  // Apply color coding to Status column (column B / col 2)
  var finalLastRow = sheet.getLastRow();
  if (finalLastRow > 1) {
    var statusRange = sheet.getRange(2, 2, finalLastRow - 1, 1);
    var statusValues = statusRange.getValues();
    for (var s = 0; s < statusValues.length; s++) {
      var statusName = statusValues[s][0];
      var color = STATUS_COLORS[statusName];
      if (color) {
        sheet.getRange(s + 2, 2, 1, 1).setBackground(color);
      }
    }
  }

  sheet.autoResizeColumns(1, headers.length);
}

// ============================================================
// DETAIL TAB - raw events (for debugging)
// ============================================================
function updateDetail(sheet, events) {
  var headers = [
    "Timestamp", "Email", "Event", "Category", "Account",
    "Subject", "Link", "From", "Template ID", "Tag", "Message ID"
  ];

  var existingHeaders = sheet.getRange(1, 1, 1, headers.length).getValues()[0];
  var hasHeaders = existingHeaders[0] === "Timestamp";

  if (!hasHeaders) {
    sheet.clear();
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
    sheet.getRange(1, 1, 1, headers.length).setBackground("#6c757d");
    sheet.getRange(1, 1, 1, headers.length).setFontColor("#ffffff");
    sheet.setFrozenRows(1);
  }

  // Collect existing keys to avoid duplicates
  var lastRow = sheet.getLastRow();
  var existingKeys = {};
  if (lastRow > 1) {
    var msgIdCol = sheet.getRange(2, 11, lastRow - 1, 1).getValues();
    var eventCol = sheet.getRange(2, 3, lastRow - 1, 1).getValues();
    var emailCol = sheet.getRange(2, 2, lastRow - 1, 1).getValues();
    for (var r = 0; r < msgIdCol.length; r++) {
      var key = emailCol[r][0] + "|" + msgIdCol[r][0] + "|" + eventCol[r][0];
      existingKeys[key] = true;
    }
  }

  // Add new events (avoid duplicates)
  var newRows = [];
  for (var i = 0; i < events.length; i++) {
    var ev = events[i];
    var key = ev.email + "|" + ev.messageId + "|" + ev.event;
    if (existingKeys[key]) continue;
    existingKeys[key] = true;

    newRows.push([
      ev.date || "", ev.email || "", ev.event || "",
      ev.category || "", ev.account || "", ev.subject || "",
      ev.link || "", ev.from || "", ev.templateId || "",
      ev.tag || "", ev.messageId || ""
    ]);
  }

  if (newRows.length > 0) {
    newRows.sort(function(a, b) {
      return (b[0] || "").localeCompare(a[0] || "");
    });
    sheet.insertRows(2, newRows.length);
    sheet.getRange(2, 1, newRows.length, headers.length).setValues(newRows);

    // Color-code event column
    for (var j = 0; j < newRows.length; j++) {
      var evt = newRows[j][2];
      var color = null;
      if (evt === "delivered" || evt === "requests") {
        color = "#e8f5e9"; // light green
      } else if (evt === "opens" || evt === "loadedByProxy") {
        color = "#d4edda"; // green
      } else if (evt === "clicks") {
        color = "#cce5ff"; // blue
      } else if (evt === "hardBounces" || evt === "softBounces" || evt === "error" || evt === "blocked") {
        color = "#f8d7da"; // red
      } else if (evt === "unsubscribed" || evt === "spamReports") {
        color = "#e2d6f3"; // purple
      }
      if (color) {
        sheet.getRange(j + 2, 3, 1, 1).setBackground(color);
      }
    }
  }
  sheet.autoResizeColumns(1, headers.length);
}
