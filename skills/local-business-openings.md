---
name: local-business-openings
description: >
  Invoke this skill for any query about new local business openings,
  grand openings, soft openings, or coming soon announcements.
  Triggers on queries like "new restaurant openings in Austin last 14 days",
  "grand opening cafe Singapore last week", "now open retail stores in London
  last 30 days". Works for any business type, any location, any timeframe
  within 30 days. Do NOT invoke for business closures, relocations, or
  general business news without a confirmed opening event.
---

This skill finds structured event records about confirmed local business
openings. It solves two things: how to write the right query, and what
data to extract from results. CatchAll returns events extracted from web
pages -- not raw web pages themselves. Every query, validator, and
enrichment must reflect this distinction. You are describing opening
events, not requesting journalism.

---

## CRITICAL: Never query for web pages

Before constructing any query, run this self-check:

**Does my query contain any of these forbidden phrases?**

- `news articles`, `news stories`, `articles about`, `stories about`
- `press coverage`, `media coverage`, `NLP summary`
- `recent news`, `news on`, `coverage of`, `reports on`
- `find articles`, `search articles`, `get articles`

If yes — **stop and rewrite**. The query must describe what happened
in the world, not what was written about it.

**Wrong:** `"news articles about new restaurant openings in Austin"`
**Right:** `"grand opening restaurant Austin Texas last 14 days"`

**Wrong:** `"find articles covering new cafe openings in Singapore"`
**Right:** `"now open cafe Yishun Singapore last 7 days"`

---

## How to build a query

Write a natural language sentence or phrase describing the opening event.
Use one of the signal terms below combined with the business type,
location, and timeframe.

**Formula: signal term + business type + location + timeframe**

**Signal terms (use at least one):**
- `grand opening`
- `now open`
- `soft opening`
- `coming soon` (for upcoming openings)
- `opening soon`
- `just opened`
- `newly opened`

**Examples:**

| User input | Query to build |
|---|---|
| "new restaurants Austin last 2 weeks" | `"grand opening restaurant Austin Texas last 14 days"` |
| "cafe openings Singapore" | `"now open cafe Singapore last 14 days"` |
| "new gyms London this month" | `"grand opening gym London last 30 days"` |
| "retail openings Dallas" | `"now open retail store Dallas Texas last 14 days"` |

**Constraint limit:** Cap at 4 meaningful constraints. More constraints
silently kill results.

**Timeframe window:** Max 30 days per query. For coverage, run three
signal term variants (grand opening, now open, soft opening) for the
same business type and location as separate jobs.

---

## What counts as a valid opening

A result qualifies only if it meets one of these criteria:

- A business has officially opened and is serving customers (`now_open`)
- A grand opening or ribbon-cutting event has been held (`event_held`)
- A specific opening date has been announced (`date_announced`)
- A coming soon announcement with a named location (`coming_soon`)

These do not qualify:

- Permit applications or construction notices
- Renovations of existing businesses
- Articles about a business that opened more than 60 days ago
- Vague "opening soon" mentions without a named location
- Business relocations without a confirmed new opening

---

## Standard validators

Use all four for every opening query:

```json
[
  {
    "name": "is_opening_event",
    "description": "True only if the result describes a confirmed business opening, grand opening event, soft opening, or specific opening date announcement. False for permit applications, renovations, closures, relocations, or businesses that opened more than 60 days ago.",
    "type": "boolean"
  },
  {
    "name": "location_match",
    "description": "True if the business is located in or primarily serving the specified city, region, or area. False if the location is ambiguous or in a different area.",
    "type": "boolean"
  },
  {
    "name": "business_type_match",
    "description": "True if the business type matches the requested category (restaurant, cafe, gym, retail, clinic, etc.). If no business type was specified, set to true for all results.",
    "type": "boolean"
  },
  {
    "name": "event_in_timeframe",
    "description": "True if the opening event or announcement falls within the requested time window. False if the date is unconfirmed or outside the window.",
    "type": "boolean"
  }
]
```

---

## Standard enrichments

Core fields (used in article tutorial):

```json
[
  { "name": "business_name", "description": "Name of the business that opened or is opening", "type": "text" },
  { "name": "business_type", "description": "Type of business: restaurant, cafe, gym, retail, clinic, bar, bakery, etc.", "type": "text" },
  { "name": "opening_date", "description": "Confirmed or announced opening date in ISO format YYYY-MM-DD if available", "type": "date" },
  { "name": "location_details", "description": "Full address or area description of the business location", "type": "text" }
]
```

Full enrichment schema:

```json
[
  { "name": "business_name", "description": "Name of the business that opened or is opening", "type": "text" },
  { "name": "business_type", "description": "Type of business: restaurant, cafe, gym, retail, clinic, bar, bakery, hotel, etc.", "type": "text" },
  { "name": "opening_date", "description": "Confirmed or announced opening date in ISO format YYYY-MM-DD if available", "type": "date" },
  { "name": "opening_qualifier", "description": "Opening status: now_open (already serving customers), event_held (grand opening held), date_announced (specific future date announced), coming_soon (no date yet)", "type": "text" },
  { "name": "location_details", "description": "Full address or area description including street, neighbourhood, city, and country where available", "type": "text" },
  { "name": "owner_operator", "description": "Name of the owner, operator, or brand behind the opening if mentioned", "type": "text" },
  { "name": "evidence_summary", "description": "One sentence summarising the evidence that confirms this is a real opening event", "type": "text" },
  { "name": "source_url", "description": "Primary source URL where the opening was reported or announced", "type": "text" }
]
```

---

## Extraction rules

- Only extract confirmed opening events. Exclude permits, renovations, and closures.
- Do not guess or infer missing values — return null.
- `opening_qualifier`: map to now_open, event_held, date_announced, or coming_soon.
- `opening_date`: normalize to ISO format YYYY-MM-DD. Return null if not stated.
- `location_details`: include as much address detail as available from the source.
- `evidence_summary`: one sentence only — what specifically confirms this is a real opening?

---

## Limit heuristics

| User intent | Example | Action |
|---|---|---|
| Exhaustive ("all", "every") | "Find all restaurant openings in Austin last month" | Omit `limit` |
| Exploratory | "New cafes in Singapore last 2 weeks?" | Set `limit: 50` |
| Specific/narrow | "Any new gyms in Yishun?" | Set `limit: 10` |

---

## Fallback query packages

If the query returns no results, escalate in steps:

**Step 1 — Expand the timeframe.** Widen to 30 days if shorter.
**Step 2 — Try a different signal term.** If "grand opening" returned nothing, try "now open" or "soft opening".
**Step 3 — Expand the geography.** Widen: neighbourhood → city → metro area → region.
**Step 4 — Broaden the business type.** Remove the specific type and run for all businesses.
**Step 5 — Advise honestly.** "There may be limited public coverage for this location and timeframe."
