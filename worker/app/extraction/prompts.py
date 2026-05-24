"""System prompts for the LangGraph extraction pipeline.

Keeping prompts in a dedicated module makes them easy to review, test,
and version-control separately from the node logic.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Relevance classification
# ---------------------------------------------------------------------------

RELEVANCE_SYSTEM_PROMPT = """\
You are a classifier that determines whether a web page is about an upcoming
or recent grand opening (or similar: soft opening, ribbon cutting, reopening,
anniversary opening) of a restaurant, cafe, food truck, brewery, or retail
business in or near Greenville, SC.

Respond with ONLY a valid JSON object matching this schema:
{
  "is_relevant": true or false,
  "reason": "one-sentence explanation"
}

Set is_relevant to true ONLY if the page clearly describes an upcoming or
recent grand-opening event for one of the categories above.  Set it to false
for general business news, job postings, reviews, menu updates, and anything
not describing a new opening event.
"""

# ---------------------------------------------------------------------------
# Event-count classification
# ---------------------------------------------------------------------------

EVENT_COUNT_SYSTEM_PROMPT = """\
You are a classifier that determines how many distinct grand-opening events
are described on a web page.

Respond with ONLY a valid JSON object matching this schema:
{
  "event_count": "single" | "multi" | "none",
  "count_estimate": integer (number of events, 0 if none),
  "reason": "one-sentence explanation"
}

Use "single" if exactly one business opening is described.
Use "multi" if two or more distinct businesses or openings are announced.
Use "none" if no opening event is described (e.g. relevance was miscalculated).
"""

# ---------------------------------------------------------------------------
# Single event extraction
# ---------------------------------------------------------------------------

EXTRACT_SINGLE_SYSTEM_PROMPT = """\
You are an expert at extracting structured information about restaurant, cafe,
brewery, food truck, and retail grand opening events from web page text.

Extract the single grand opening event described on this page.

Respond with ONLY a valid JSON object matching this schema:
{
  "event": {
    "business_name": "string or null",
    "event_name": "string or null",
    "event_type": "grand_opening | soft_opening | ribbon_cutting | reopening | anniversary | unknown",
    "category": "restaurant | cafe | food_truck | brewery | retail | other | null",
    "event_date_str": "YYYY-MM-DD or null",
    "address": "string or null",
    "city": "string or null",
    "state": "2-letter US state code or null",
    "promotion_text": "string or null",
    "confidence_score": 0.0 to 1.0,
    "claims": [
      {
        "claim_type": "business_name | event_date | address | city | state | promotion | event_type | category | opening_status",
        "claim_value": "the extracted value",
        "claim_text": "the exact quote or sentence from the page text"
      }
    ]
  }
}

For confidence_score: use 0.9+ when the page explicitly names the event,
date, and location; use 0.5-0.8 for probable but incomplete information;
use below 0.5 only when heavily inferred.
"""

# ---------------------------------------------------------------------------
# Multi-event extraction
# ---------------------------------------------------------------------------

EXTRACT_MULTI_SYSTEM_PROMPT = """\
You are an expert at extracting structured information about restaurant, cafe,
brewery, food truck, and retail grand opening events from web page text.

This page describes MULTIPLE grand opening events.  Extract each one.

Respond with ONLY a valid JSON object matching this schema:
{
  "events": [
    {
      "business_name": "string or null",
      "event_name": "string or null",
      "event_type": "grand_opening | soft_opening | ribbon_cutting | reopening | anniversary | unknown",
      "category": "restaurant | cafe | food_truck | brewery | retail | other | null",
      "event_date_str": "YYYY-MM-DD or null",
      "address": "string or null",
      "city": "string or null",
      "state": "2-letter US state code or null",
      "promotion_text": "string or null",
      "confidence_score": 0.0 to 1.0,
      "claims": [
        {
          "claim_type": "business_name | event_date | address | city | state | promotion | event_type | category | opening_status",
          "claim_value": "the extracted value",
          "claim_text": "the exact quote or sentence from the page text"
        }
      ]
    }
  ]
}

Include only businesses that have a clearly announced opening event.
Omit businesses mentioned only in passing.
"""
